"""Collect index quotes and market-wide facts; a failed source is recorded, not fatal."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from tradingagents.dataflows.vendors.a_share import akshare_patch  # noqa: F401  (installs the Eastmoney wrapper)
from tradingagents.dataflows.vendors.a_share import http
from tradingagents.dataflows.vendors.a_share.news import get_global_news
from tradingagents.dataflows.vendors.a_share.types import DailyBar

if TYPE_CHECKING:
    from market.fundamentals import Fundamentals

logger = logging.getLogger(__name__)


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
    source: str | None = None


@dataclass
class Sentiment:
    limit_up: int | None = None
    limit_down: int | None = None
    broken: int | None = None
    broken_rate: float | None = None
    max_streak: int | None = None
    as_of: str | None = None
    source: str | None = None


@dataclass
class Industries:
    gainers: list[tuple[str, float]]
    losers: list[tuple[str, float]]
    as_of: str
    note: str | None = None
    source: str | None = None


@dataclass
class MarketNews:
    title: str
    published_at: str
    source: str
    url: str | None = None
    note: str = "媒体口径，未核实"


@dataclass
class NewsResult:
    items: list[MarketNews]
    gap: str | None = None


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


def _parse_sse_turnover(frame, trade_date: str) -> Turnover | None:
    """SSE daily stock turnover (亿元) from the ``stock_deal_daily_sse`` frame."""
    try:
        cells = frame.loc[frame["单日情况"] == "成交金额", "股票"]
    except (KeyError, TypeError):
        return None
    if cells.empty:
        return None
    try:
        value = float(cells.iloc[0])
    except (TypeError, ValueError):
        return None
    if value != value:  # NaN placeholder from akshare
        return None
    return Turnover(
        sh=value, note="上交所-股票（含B股）", as_of=trade_date, source="上交所"
    )


def fetch_sse_turnover(trade_date: str) -> Turnover | None:
    """SSE stock turnover for one session; network errors propagate to the caller."""
    import akshare as ak

    # akshare renamed the function; support both spellings.
    fetch = getattr(ak, "stock_deal_daily_sse", None) or getattr(ak, "stock_sse_deal_daily")
    return _parse_sse_turnover(fetch(date=trade_date.replace("-", "")), trade_date)


def _parse_szse_turnover(frame, trade_date: str) -> Turnover | None:
    """SZSE daily stock turnover (亿元) from the ``stock_summary_szse`` frame."""
    try:
        cells = frame.loc[frame["证券类别"] == "股票", "成交金额"]
    except (KeyError, TypeError):
        return None
    if cells.empty:
        return None
    try:
        value = float(cells.iloc[0]) / 1e8  # akshare reports 元
    except (TypeError, ValueError):
        return None
    if value != value:  # NaN placeholder from akshare
        return None
    return Turnover(
        sz=value,
        note="深交所-股票（含B股与创业板）",
        as_of=trade_date,
        source="深交所",
    )


def fetch_szse_turnover(trade_date: str) -> Turnover | None:
    """SZSE stock turnover for one session; network errors propagate to the caller."""
    import akshare as ak

    # akshare renamed the function; support both spellings.
    fetch = getattr(ak, "stock_summary_szse", None) or getattr(ak, "stock_szse_summary")
    return _parse_szse_turnover(fetch(date=trade_date.replace("-", "")), trade_date)


def build_turnover(sh: Turnover | None, sz: Turnover | None, trade_date: str) -> Turnover:
    """Combined same-day turnover; total needs both sides, 20-day stats stay unset."""
    sh_value = sh.sh if sh else None
    sz_value = sz.sz if sz else None
    both = sh_value is not None and sz_value is not None
    if both:
        source = "上交所/深交所"
    elif sh_value is not None:
        source = sh.source if sh else None
    else:
        source = sz.source if sz else None
    return Turnover(
        sh=sh_value,
        sz=sz_value,
        total=sh_value + sz_value if both else None,
        note="沪深股票成交额（含B股）；量能倍数见指数小节（指数成交量口径）",
        as_of=trade_date,
        source=source,
    )


def _fetch_turnover_side(source: str, fetch, trade_date: str) -> Turnover | None:
    """One exchange's turnover; a source error yields ``None`` instead of aborting."""
    try:
        return fetch(trade_date)
    except Exception as exc:
        logger.debug("turnover fetch failed for %s: %s", source, exc)
        return None


def fetch_turnover(trade_date: str) -> Turnover:
    """SSE and SZSE stock turnover for the same session; a failed side stays empty."""
    return build_turnover(
        _fetch_turnover_side("SSE", fetch_sse_turnover, trade_date),
        _fetch_turnover_side("SZSE", fetch_szse_turnover, trade_date),
        trade_date,
    )


def _parse_limit_up(frame) -> tuple[int | None, int | None]:
    """Limit-up count and highest streak from the ``stock_zt_pool_em`` frame."""
    if frame.empty:
        return 0, None
    if "连板数" not in frame:
        return len(frame), None
    return len(frame), int(frame["连板数"].max())


def fetch_limit_up(trade_date: str) -> tuple[int | None, int | None]:
    """Eastmoney limit-up pool count and highest streak; errors propagate."""
    import akshare as ak

    return _parse_limit_up(ak.stock_zt_pool_em(date=trade_date.replace("-", "")))


def _parse_pool_count(frame) -> int:
    """Stock count in a pool frame; an empty frame means zero."""
    return len(frame)


def fetch_broken_pool(trade_date: str) -> int:
    """Eastmoney broken-board pool count; errors propagate."""
    import akshare as ak

    return _parse_pool_count(ak.stock_zt_pool_zbgc_em(date=trade_date.replace("-", "")))


def fetch_limit_down_pool(trade_date: str) -> int:
    """Eastmoney limit-down pool count; errors propagate."""
    import akshare as ak

    return _parse_pool_count(ak.stock_zt_pool_dtgc_em(date=trade_date.replace("-", "")))


def build_sentiment(
    limit_up: int | None,
    max_streak: int | None,
    broken: int | None,
    limit_down: int | None,
    trade_date: str,
) -> Sentiment:
    """Assemble the sentiment record; ``broken_rate`` needs both limit-up and broken counts."""
    from market.rules import broken_rate  # function-local: market.rules imports market.fetch

    return Sentiment(
        limit_up=limit_up,
        max_streak=max_streak,
        broken=broken,
        limit_down=limit_down,
        broken_rate=broken_rate(limit_up, broken),
        as_of=trade_date,
        source="东财",
    )


def _fetch_sentiment_pool(name: str, fetch, trade_date: str):
    """One sentiment pool; a source error yields ``None`` instead of aborting."""
    try:
        return fetch(trade_date)
    except Exception as exc:
        logger.debug("sentiment %s pool fetch failed: %s", name, exc)
        return None


def fetch_sentiment(trade_date: str) -> Sentiment:
    """Limit-up, broken and limit-down pools fetched independently; a failed pool stays empty."""
    limit_up_result = _fetch_sentiment_pool("limit-up", fetch_limit_up, trade_date)
    limit_up, max_streak = limit_up_result if limit_up_result is not None else (None, None)
    return build_sentiment(
        limit_up,
        max_streak,
        _fetch_sentiment_pool("broken", fetch_broken_pool, trade_date),
        _fetch_sentiment_pool("limit-down", fetch_limit_down_pool, trade_date),
        trade_date,
    )


def _parse_industries(frame, as_of: str) -> Industries:
    """Top and bottom five THS industry boards by change pct; an empty frame stays empty."""
    import pandas as pd

    if frame is None or frame.empty or "板块" not in frame or "涨跌幅" not in frame:
        return Industries(
            gainers=[], losers=[], as_of=as_of, note="行业榜无数据", source="同花顺"
        )
    pct = pd.to_numeric(frame["涨跌幅"], errors="coerce")
    valid = frame.assign(涨跌幅=pct).dropna(subset=["涨跌幅"])
    ranked = sorted(
        (
            (str(name), float(value))
            for name, value in zip(valid["板块"], valid["涨跌幅"], strict=True)
        ),
        key=lambda row: row[1],
        reverse=True,
    )
    return Industries(
        gainers=ranked[:5],
        losers=sorted(ranked[-5:], key=lambda row: row[1]),
        as_of=as_of,
        source="同花顺",
    )


def fetch_industries(trade_date: str) -> Industries:
    """THS industry board snapshot; historical dates are refused, the board is current-only."""
    if trade_date < datetime.now().strftime("%Y-%m-%d"):
        return Industries(
            gainers=[], losers=[], as_of=trade_date, note="仅当日，历史不可用",
            source="同花顺",
        )
    import akshare as ak

    as_of = datetime.now().strftime("%Y-%m-%d %H:%M")
    return _parse_industries(ak.stock_board_industry_summary_ths(), as_of)


_NEWS_LINE = re.compile(
    r"^- \[(?P<source>[^\]]+)\] (?P<published_at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) (?P<title>.+)$"
)


def _parse_global_news(text: str) -> list[MarketNews]:
    """Parse ``get_global_news`` markdown; sentinels, headings and malformed lines yield nothing."""
    stripped = text.strip()
    if not stripped or stripped.startswith(("DATA_UNAVAILABLE:", "NO_DATA_AVAILABLE:")):
        return []
    return [
        MarketNews(**match.groupdict())
        for line in stripped.splitlines()
        if (match := _NEWS_LINE.match(line)) and "北向" not in match.group("title")
    ]


def fetch_news(trade_date: str, look_back_days: int = 7, limit: int = 10) -> NewsResult:
    """Market-wide flashes; a failed or empty source is recorded as a gap, never raised."""
    try:
        text = get_global_news(trade_date, look_back_days=look_back_days, limit=limit)
    except Exception as exc:
        logger.debug("news fetch failed: %s", exc)
        return NewsResult([], gap=f"news: {type(exc).__name__}: {exc}")
    items = _parse_global_news(text)[:limit]
    return NewsResult(items) if items else NewsResult([], gap="news: 无条目")


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
    flags: list = field(default_factory=list)
    fundamentals: "Fundamentals | None" = None
    cutoff: str | None = None
