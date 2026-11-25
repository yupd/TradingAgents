"""Which market a code belongs to, and the vendor config that market runs on."""

from __future__ import annotations

import copy

from .symbols import parse_ashare

_METHOD_KEYS = ("core_stock_apis", "technical_indicators", "fundamental_data", "news_data", "signal_data")


def market_of(raw: str) -> str:
    """``CN`` for a mainland code, ``HK`` for a ``.HK`` code, else ``ValueError``."""
    text = (raw or "").strip().upper()
    if text.endswith(".HK"):
        return "HK"
    parse_ashare(text)
    return "CN"


def apply_market_config(raw: str, config: dict) -> dict:
    """Return a copy of ``config`` whose data vendors serve this market."""
    market = market_of(raw)
    cfg = copy.deepcopy(config)
    vendors = dict(cfg.get("data_vendors") or {})
    for key in _METHOD_KEYS:
        if market == "CN":
            vendors[key] = "a_share"
        else:
            vendors[key] = "" if key == "signal_data" else "yfinance"
    cfg["data_vendors"] = vendors
    return cfg


def apply_default_market_config(raw: str, config: dict) -> dict:
    """Route A-share and HK codes as their markets need; other codes keep yfinance."""
    try:
        return apply_market_config(raw, config)
    except ValueError:
        cfg = copy.deepcopy(config)
        vendors = dict(cfg.get("data_vendors") or {})
        for key in ("core_stock_apis", "technical_indicators", "fundamental_data", "news_data"):
            vendors[key] = "yfinance"
        vendors["signal_data"] = ""
        cfg["data_vendors"] = vendors
        return cfg
