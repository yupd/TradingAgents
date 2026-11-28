import re

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


def test_kline_patterns_uses_local_bars(monkeypatch):
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: BARS)
    text = q.get_kline_patterns("600519", "2026-11-21")
    assert "K线形态" in text
    assert "Source: mootdx" in text and "As of: 2026-11-21" in text


def test_kline_patterns_all_sources_fail(monkeypatch):
    for name in ("_mootdx_bars", "_em_bars", "_tencent_bars", "_sina_bars"):
        monkeypatch.setattr(q, name, lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    text = q.get_kline_patterns("600519", "2026-11-21")
    assert text.startswith("DATA_UNAVAILABLE")


def test_kline_patterns_historical_never_reads_live(monkeypatch):
    monkeypatch.setattr(
        q, "get_snapshot", lambda *a: (_ for _ in ()).throw(AssertionError("live used")))
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: BARS)
    text = q.get_kline_patterns("600519", "2026-11-21")
    assert "Source: mootdx" in text


def test_kline_patterns_excludes_bars_after_curr_date(monkeypatch):
    future = pd.concat([BARS, pd.DataFrame({
        "date": ["2026-11-24"], "open": [10.6], "high": [11.0],
        "low": [10.5], "close": [10.9], "volume": [1500]})], ignore_index=True)
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: future)
    text = q.get_kline_patterns("600519", "2026-11-21")
    assert "2026-11-24" not in text
    assert "As of: 2026-11-21" in text


def test_kline_patterns_keeps_trend_context_before_window(monkeypatch):
    rows = []
    for i, close in enumerate([10.0, 9.8, 9.6, 9.4, 9.2, 9.0]):
        rows.append({"date": f"2026-11-{i + 1:02d}", "open": close,
                     "high": close * 1.01, "low": close * 0.99,
                     "close": close, "volume": 1000})
    rows.append({"date": "2026-11-07", "open": 9.2, "high": 9.35,
                 "low": 8.5, "close": 9.3, "volume": 1000})
    for i in range(4):
        rows.append({"date": f"2026-11-{8 + i:02d}", "open": 9.3, "high": 9.4,
                     "low": 9.2, "close": 9.3, "volume": 1000})
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: pd.DataFrame(rows))
    text = q.get_kline_patterns("600519", "2026-11-11", 5)
    assert "锤子线" in text
    assert "历史不足" not in text


def test_kline_patterns_clamps_non_positive_window(monkeypatch):
    idx = pd.date_range("2026-08-01", periods=70, freq="D")
    frame = pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "open": 10.0,
                          "high": 10.2, "low": 9.8, "close": 10.0,
                          "volume": 1000})
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: frame)
    text = q.get_kline_patterns("600519", idx[-1].strftime("%Y-%m-%d"), 0)
    assert "窗口：60 根" in text


PROMPT_INDICATORS = ("close_50_sma", "close_200_sma", "close_10_ema", "macd",
                     "macds", "macdh", "rsi", "boll", "boll_ub", "boll_lb",
                     "atr", "vwma")


def _long_frame(periods=250):
    import numpy as np
    idx = pd.date_range("2025-01-01", periods=periods, freq="D")
    close = np.linspace(10.0, 20.0, periods)
    return pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "open": close,
                         "high": close + 0.3, "low": close - 0.3,
                         "close": close, "volume": 1000.0})


@pytest.mark.parametrize("indicator", PROMPT_INDICATORS)
def test_every_prompt_indicator_resolves(monkeypatch, indicator):
    frame = _long_frame()
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: frame)
    text = q.get_indicators("600519", indicator, frame["date"].iloc[-1], 30)
    assert "UNSUPPORTED_INDICATOR" not in text, text
    assert re.search(r"\| \d{4}-\d{2}-\d{2} \| [-\d.]+ \|", text), text


def test_short_history_returns_data_unavailable(monkeypatch):
    frame = _long_frame(60)
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: frame)
    text = q.get_indicators("600519", "close_200_sma", frame["date"].iloc[-1])
    assert text.startswith("DATA_UNAVAILABLE"), text
    assert "close_200_sma" in text and "needs at least 200 bars" in text


def test_short_history_allows_10_ema(monkeypatch):
    frame = _long_frame(60)
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: frame)
    text = q.get_indicators("600519", "close_10_ema", frame["date"].iloc[-1])
    assert "DATA_UNAVAILABLE" not in text
    assert re.search(r"\| \d{4}-\d{2}-\d{2} \| [-\d.]+ \|", text), text


def test_unknown_indicator_still_rejected(monkeypatch):
    monkeypatch.setattr(q, "_bars_until",
                        lambda *a: (_ for _ in ()).throw(AssertionError("fetch used")))
    assert q.get_indicators("600519", "mfi", "2026-11-21") == "UNSUPPORTED_INDICATOR: mfi"


def test_close_200_sma_matches_rolling_mean(monkeypatch):
    import numpy as np
    frame = _long_frame()
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: frame)
    text = q.get_indicators("600519", "close_200_sma", frame["date"].iloc[-1], 30)
    last = re.findall(r"\| \d{4}-\d{2}-\d{2} \| ([-\d.]+) \|", text)[-1]
    expected = np.linspace(10.0, 20.0, 250)[-200:].mean()
    assert abs(float(last) - expected) < 1e-3


def test_partial_window_rows_are_not_emitted(monkeypatch):
    frame = _long_frame(210)
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: frame)
    text = q.get_indicators("600519", "close_200_sma", frame["date"].iloc[-1], 30)
    dates = re.findall(r"\| (\d{4}-\d{2}-\d{2}) \|", text)
    assert len(dates) == 11
    assert dates[0] == frame["date"].iloc[199]


def test_non_positive_look_back_clamps(monkeypatch):
    frame = _long_frame()
    monkeypatch.setattr(q, "_mootdx_bars", lambda *a: frame)
    text = q.get_indicators("600519", "rsi", frame["date"].iloc[-1], 0)
    assert re.search(r"\| \d{4}-\d{2}-\d{2} \| [-\d.]+ \|", text), text
