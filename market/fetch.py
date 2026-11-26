"""Collect index quotes and market-wide facts; a failed source is recorded, not fatal."""

from __future__ import annotations

from dataclasses import dataclass, field


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
