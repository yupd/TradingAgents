"""Collect index quotes and market-wide facts; a failed source is recorded, not fatal."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from tradingagents.dataflows.vendors.a_share import http
from tradingagents.dataflows.vendors.a_share.types import DailyBar


@dataclass
class IndexQuote:
    name: str
    code: str
    close: float | None = None
    change_pct: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    return_60d: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    volume_ratio: float | None = None
    source: str | None = None
    as_of: str | None = None


@dataclass
class Turnover:
    sh: float | None = None
    sz: float | None = None
    total: float | None = None
    avg20: float | None = None
    ratio: float | None = None
    note: str | None = None
    as_of: str | None = None


@dataclass
class Sentiment:
    limit_up: int | None = None
    limit_down: int | None = None
    broken: int | None = None
    broken_rate: float | None = None
    max_streak: int | None = None
    as_of: str | None = None


@dataclass(frozen=True)
class IndexSpec:
    name: str
    code: str
    exchange: str


INDEXES: tuple[IndexSpec, ...] = (
    IndexSpec(name="上证", code="sh000001", exchange="SH"),
    IndexSpec(name="深成", code="sz399001", exchange="SZ"),
    IndexSpec(name="创业板", code="sz399006", exchange="SZ"),
    IndexSpec(name="沪深300", code="sh000300", exchange="SH"),
    IndexSpec(name="科创50", code="sh000688", exchange="SH"),
)


def _tencent_index_bars(spec: IndexSpec, start: str, end: str) -> list[DailyBar]:
    """Daily qfq bars for one index; empty when Tencent has no rows."""
    response = http.em_get(
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
        params={"param": f"{spec.code},day,{start},{end},640,qfq"},
    )
    data = response.json().get("data", {}).get(spec.code, {})
    rows = data.get("qfqday") or data.get("day") or []
    bars = []
    for row in rows:
        date, open_, close, high, low, volume = (str(value) for value in row[:6])
        if start <= date <= end:
            bars.append(
                DailyBar(
                    date=date,
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume),
                    source="tencent",
                    as_of=date,
                )
            )
    return bars


def _sina_index_bars(spec: IndexSpec, start: str, end: str) -> list[DailyBar]:
    """Daily bars for one index from Sina's JSONP kline API."""
    response = http.em_get(
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/x/CN_MarketDataService.getKLineData",
        params={"symbol": spec.code, "scale": 240, "ma": "no", "datalen": 1023},
    )
    text = response.text
    rows = json.loads(text[text.index("(") + 1 : text.rindex(")")])
    bars = []
    for row in rows:
        date = str(row["day"])
        if start <= date <= end:
            bars.append(
                DailyBar(
                    date=date,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    source="sina",
                    as_of=date,
                )
            )
    return bars


def _em_index_bars(spec: IndexSpec, start: str, end: str) -> list[DailyBar]:
    """Daily bars for one index from Eastmoney's kline API."""
    response = http.em_get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": f"{1 if spec.exchange == 'SH' else 0}.{spec.code[2:]}",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56",
            "klt": 101,
            "fqt": 1,
            "beg": start.replace("-", ""),
            "end": end.replace("-", ""),
        },
    )
    klines = (response.json().get("data") or {}).get("klines") or []
    bars = []
    for line in klines:
        date, open_, close, high, low, volume = (str(value) for value in line.split(",")[:6])
        if start <= date <= end:
            bars.append(
                DailyBar(
                    date=date,
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume),
                    source="eastmoney",
                    as_of=date,
                )
            )
    return bars


def fetch_index_bars(spec: IndexSpec, start: str, end: str) -> list[DailyBar] | None:
    """The first source that returns bars wins; ``None`` when all three fail."""
    for fetch in (_tencent_index_bars, _sina_index_bars, _em_index_bars):
        try:
            bars = fetch(spec, start, end)
        except Exception:
            continue
        if bars:
            return bars
    return None


def fetch_indices(trade_date: str) -> list[IndexQuote]:
    """All five index quotes in ``INDEXES`` order; a failed index keeps ``None`` metrics."""
    from market.rules import build_index_quote

    start_day = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=400)
    start = start_day.strftime("%Y-%m-%d")
    quotes = []
    for spec in INDEXES:
        try:
            quote = build_index_quote(spec, fetch_index_bars(spec, start, trade_date) or [])
        except Exception:
            quote = build_index_quote(spec, [])
        quotes.append(quote)
    return quotes


@dataclass
class MarketFacts:
    trade_date: str
    requested_date: str | None = None
    as_of: str | None = None
    indices: list[IndexQuote] = field(default_factory=list)
    turnover: Turnover | None = None
    sentiment: Sentiment | None = None
    industries: object | None = None
    news: list[object] = field(default_factory=list)
    trend: object | None = None
    gaps: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
