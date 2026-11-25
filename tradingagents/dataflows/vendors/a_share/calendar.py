"""A-share trading calendar, from the Sina calendar AkShare exposes."""

from __future__ import annotations

from . import akshare_patch  # noqa: F401  (installs the Eastmoney wrapper)
from datetime import date

import pandas as pd

_dates: tuple[date, ...] | None = None


def _load_dates() -> tuple[date, ...]:
    """Every trading day the calendar source knows, oldest first."""
    global _dates
    if _dates is None:
        import akshare as ak

        frame = ak.tool_trade_date_hist_sina()
        _dates = tuple(pd.to_datetime(frame["trade_date"]).dt.date.tolist())
    return _dates


def get_trade_dates() -> tuple[date, ...]:
    return _load_dates()


def is_trade_date(value: str) -> bool:
    return date.fromisoformat(value) in set(_load_dates())


def previous_trade_date(value: str) -> str:
    """The latest trading day on or before ``value``."""
    target = date.fromisoformat(value)
    eligible = [day for day in _load_dates() if day <= target]
    if not eligible:
        raise ValueError(f"no trading day on or before {value}")
    return eligible[-1].isoformat()
