"""Deterministic market trend signals computed from the facts, never from the model."""

from __future__ import annotations

from market.fetch import IndexQuote, IndexSpec
from tradingagents.dataflows.vendors.a_share.types import DailyBar


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
