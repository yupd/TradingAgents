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
