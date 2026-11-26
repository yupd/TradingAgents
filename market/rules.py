"""Deterministic market trend signals computed from the facts, never from the model."""

from __future__ import annotations

from dataclasses import dataclass

from market.fetch import IndexQuote, IndexSpec
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
    if close_above_ma20 and ma20_above_ma60 and return_20d_positive:
        level = "上行"
    elif not (close_above_ma20 or ma20_above_ma60 or return_20d_positive):
        level = "下行"
    else:
        level = "震荡"
    return Trend(level, close_above_ma20, ma20_above_ma60, return_20d_positive)


def broken_rate(limit_up: int | None, broken: int | None) -> float | None:
    """Broken-board rate in percent points; ``None`` when inputs are missing or both zero."""
    if limit_up is None or broken is None:
        return None
    total = limit_up + broken
    if total == 0:
        return None
    return broken / total * 100


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
