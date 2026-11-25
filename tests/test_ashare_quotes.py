import pandas as pd
import pytest

import tradingagents.dataflows.vendors.a_share.quotes as q
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

BARS = pd.DataFrame({"date": ["2026-11-20", "2026-11-21"], "open": [10.0, 10.2],
                     "high": [10.5, 10.6], "low": [9.9, 10.1], "close": [10.2, 10.4],
                     "volume": [1000, 1200]})


def test_daily_uses_mootdx_first(monkeypatch):
    monkeypatch.setattr(q, "_mootdx_bars", lambda sym, s, e: BARS)
    monkeypatch.setattr(q, "_em_bars", lambda *a: (_ for _ in ()).throw(AssertionError("fallback used")))
    bars = q.get_daily_bars(parse_ashare("600519"), "2026-11-18", "2026-11-21")
    assert [b.close for b in bars] == [10.2, 10.4]
    assert bars[0].source == "mootdx"


def test_daily_falls_back_to_eastmoney_then_tencent(monkeypatch):
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(q, "_em_bars", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(q, "_tencent_bars", lambda sym, s, e: BARS)
    bars = q.get_daily_bars(parse_ashare("000001"), "2026-11-18", "2026-11-21")
    assert bars[0].source == "tencent"


def test_all_fail_returns_sentinel(monkeypatch):
    for name in ("_mootdx_bars", "_em_bars", "_tencent_bars", "_sina_bars"):
        monkeypatch.setattr(q, name, lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    text = q.get_stock_data("600519", "2026-11-18", "2026-11-21")
    assert text.startswith(("NO_DATA_AVAILABLE", "DATA_UNAVAILABLE"))


def test_format_has_source_and_as_of(monkeypatch):
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: BARS)
    text = q.get_stock_data("600519", "2026-11-18", "2026-11-21")
    assert "Source: mootdx" in text and "As of: 2026-11-21" in text


def test_indicators_use_local_bars(monkeypatch):
    import numpy as np
    idx = pd.date_range("2026-08-01", periods=60, freq="D")
    bars = pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "open": 10.0,
                         "high": np.linspace(10, 11, 60), "low": 9.5,
                         "close": np.linspace(10, 11, 60), "volume": 1000})
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: bars)
    text = q.get_indicators("600519", "rsi", "2026-09-29", 30)
    assert "Source: mootdx" in text and "RSI" in text


def test_verified_snapshot_historical_never_reads_live(monkeypatch):
    monkeypatch.setattr(q, "get_snapshot", lambda *a: (_ for _ in ()).throw(AssertionError("live used")))
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: BARS)
    text = q.get_verified_market_snapshot("600519", "2026-11-21")
    assert "2026-11-21" in text and "Source: mootdx" in text


def test_em_get_retries_three_times(monkeypatch):
    import tradingagents.dataflows.vendors.a_share.http as h
    calls = {"n": 0}

    def down(*a, **k):
        calls["n"] += 1
        raise RuntimeError("down")

    monkeypatch.setattr(h.requests, "get", down)
    monkeypatch.setattr(h.time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError):
        h.em_get("https://push2.eastmoney.com/api/qt/stock/get")
    assert calls["n"] == 3
