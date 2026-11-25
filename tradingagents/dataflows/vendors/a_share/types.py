"""Typed values shared by the A-share vendor modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AStockSymbol:
    """A mainland-listed stock: its six-digit code and exchange."""

    code: str
    exchange: str  # "SH" | "SZ" | "BJ"

    @property
    def yahoo(self) -> str:
        """The symbol as Yahoo spells it (Shanghai is ``.SS``)."""
        return f"{self.code}.{'SS' if self.exchange == 'SH' else self.exchange}"

    @property
    def display(self) -> str:
        """The symbol as reports spell it."""
        return f"{self.code}.{self.exchange}"


@dataclass(frozen=True)
class DailyBar:
    """One completed session's OHLCV, with the source it came from."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    as_of: str


@dataclass(frozen=True)
class Snapshot:
    """A live quote and the valuation fields the brief reports."""

    code: str
    name: str
    price: float
    prev_close: float
    change_pct: float
    volume: float
    turnover_rate: float | None
    pe_ttm: float | None
    pb: float | None
    source: str
    as_of: str


@dataclass(frozen=True)
class StatementRow:
    """One reported period, with the date it was announced."""

    period: str
    publish_date: str | None
    values: dict[str, float]
    source: str
