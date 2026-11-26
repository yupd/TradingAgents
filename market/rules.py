"""Deterministic market trend signals computed from the facts, never from the model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from market.fetch import IndexQuote, IndexSpec, Industries, NewsResult, Sentiment, Turnover
from tradingagents.dataflows.vendors.a_share.calendar import previous_trade_date
from tradingagents.dataflows.vendors.a_share.types import DailyBar


@dataclass(frozen=True)
class Trend:
    level: str
    close_above_ma20: bool | None
    ma20_above_ma60: bool | None
    return_20d_positive: bool | None


def classify_trend(quote: IndexQuote) -> Trend:
    """Three-condition decision table; 上行 needs all three, 下行 none, otherwise 震荡."""
    close, ma20, ma60, return_20d = (
        quote.close,
        quote.ma20,
        quote.ma60,
        quote.return_20d,
    )
    if None in (close, ma20, ma60, return_20d):
        return Trend("无法判定", None, None, None)
    close_above_ma20 = close > ma20
    ma20_above_ma60 = ma20 > ma60
    return_20d_positive = return_20d > 0
    # Strict inequalities on both sides: equality counts as 震荡, not 下行.
    if close_above_ma20 and ma20_above_ma60 and return_20d_positive:
        level = "上行"
    elif close < ma20 and ma20 < ma60 and return_20d < 0:
        level = "下行"
    else:
        level = "震荡"
    return Trend(level, close_above_ma20, ma20_above_ma60, return_20d_positive)


@dataclass(frozen=True)
class Flag:
    kind: str
    label: str
    detail: str


def compute_flags(indices: list[IndexQuote], sentiment: Sentiment | None) -> list[Flag]:
    """Deterministic flags in fixed order: volume, limit ratio, broken rate, 20-day dispersion."""
    flags: list[Flag] = []
    hs300 = next((quote for quote in indices if quote.code == "sh000300"), None)
    if hs300 is not None and hs300.volume_ratio is not None:
        detail = f"沪深300 20 日量能倍数 {hs300.volume_ratio:.1f}"
        if hs300.volume_ratio >= 1.2:
            flags.append(Flag("volume_up", "放量", detail))
        elif hs300.volume_ratio <= 0.8:
            flags.append(Flag("volume_down", "缩量", detail))
    if sentiment is not None:
        if sentiment.limit_up is not None and sentiment.limit_down is not None:
            flags.append(
                Flag(
                    "limit_ratio",
                    "涨停/跌停",
                    f"涨停 {sentiment.limit_up} / 跌停 {sentiment.limit_down}",
                )
            )
        if sentiment.broken_rate is not None:
            flags.append(Flag("broken_rate", "炸板率", f"{sentiment.broken_rate:.1f}%"))
    available = [
        (quote.return_20d, quote.name) for quote in indices if quote.return_20d is not None
    ]
    if len(available) >= 2:
        strongest = max(available)
        weakest = min(available)
        spread = strongest[0] - weakest[0]
        flags.append(
            Flag(
                "dispersion",
                "指数 20 日分化",
                f"极差 {spread:.1f} 个百分点（最强 {strongest[1]} {strongest[0]:+.1f}%，"
                f"最弱 {weakest[1]} {weakest[0]:+.1f}%）",
            )
        )
    return flags


_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def resolve_trade_date(
    requested: str | None = None, today: str | None = None
) -> tuple[str, str | None]:
    """Normalize the requested date to the latest trading day, recording a calendar gap."""
    target = requested or today or date.today().isoformat()
    # strptime accepts unpadded parts like 2026-1-1; require the exact shape too.
    if not _ISO_DATE.fullmatch(target):
        raise ValueError(f"invalid date {target!r}, expected YYYY-MM-DD")
    datetime.strptime(target, "%Y-%m-%d")
    try:
        return previous_trade_date(target), None
    except Exception as exc:
        return target, f"calendar: {type(exc).__name__}: {exc}"


def broken_rate(limit_up: int | None, broken: int | None) -> float | None:
    """Broken-board rate in percent points; ``None`` when inputs are missing or both zero."""
    if limit_up is None or broken is None:
        return None
    total = limit_up + broken
    if total == 0:
        return None
    return broken / total * 100


def collect_gaps(
    indices: list[IndexQuote],
    turnover: Turnover | None,
    sentiment: Sentiment | None,
    industries: Industries | None,
    news: NewsResult | None,
    extra: list[str] | None = None,
) -> list[str]:
    """Every unavailable item as one line, in fixed order, de-duplicated."""
    gaps: list[str] = []
    for quote in indices:
        if quote.close is None:
            gaps.append(f"indices: {quote.name} 取数失败")
    if turnover is None:
        gaps.append("turnover: 成交额不可用")
    else:
        if turnover.sh is None:
            gaps.append("turnover: 沪市成交额不可用")
        if turnover.sz is None:
            gaps.append("turnover: 深市成交额不可用")
    if sentiment is None:
        gaps.append("sentiment: 情绪数据不可用")
    else:
        if sentiment.limit_up is None:
            gaps.append("sentiment: 涨停池不可用")
        if sentiment.broken is None:
            gaps.append("sentiment: 炸板池不可用")
        if sentiment.limit_down is None:
            gaps.append("sentiment: 跌停池不可用")
    if industries is None:
        gaps.append("industries: 行业榜不可用")
    elif industries.note:
        gaps.append(f"industries: {industries.note}")
    if news is not None and news.gap:
        gaps.append(news.gap)
    gaps.extend(extra or [])
    return list(dict.fromkeys(gaps))


def _return(closes: list[float], days: int) -> float | None:
    """Percent change over ``days`` sessions; ``None`` when history is short."""
    if len(closes) <= days:
        return None
    return (closes[-1] / closes[-1 - days] - 1) * 100


def _mean_last(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def build_index_quote(spec: IndexSpec, bars: list[DailyBar]) -> IndexQuote:
    """Multi-period metrics for one index from its daily bars, in percent points."""
    if not bars:
        return IndexQuote(name=spec.name, code=spec.code)
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]
    last = bars[-1]
    quote = IndexQuote(
        name=spec.name,
        code=spec.code,
        close=last.close,
        source=last.source,
        as_of=last.as_of,
    )
    if len(closes) >= 2:
        quote.change_pct = (closes[-1] / closes[-2] - 1) * 100
    quote.return_5d = _return(closes, 5)
    quote.return_20d = _return(closes, 20)
    quote.return_60d = _return(closes, 60)
    quote.ma20 = _mean_last(closes, 20)
    quote.ma60 = _mean_last(closes, 60)
    if len(volumes) >= 21:
        baseline = _mean_last(volumes[:-1], 20)
        if baseline:
            quote.volume_ratio = volumes[-1] / baseline
    return quote
