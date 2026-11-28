"""Assembly of the four fundamentals blocks and the history-mode short circuit."""

import pandas as pd
import pytest

from market.fundamentals import (
    Earnings,
    Fundamentals,
    MacroBlock,
    MacroItem,
    Margin,
    Valuation,
    fetch_fundamentals,
    fetch_margin,
    fetch_valuation,
)

TRADE_DATE = "2026-11-26"


@pytest.fixture(autouse=True)
def _offline_danjuan(monkeypatch):
    monkeypatch.setattr(
        "market.fundamentals._danjuan_index", lambda spec, trade_date: None
    )


def _blocks():
    return (
        MacroBlock(items=[MacroItem("CPI", 0.3, "%", "2026年10月", "源")]),
        Valuation(pe_ttm=12.6),
        Margin(sh=1.0, sz=2.0, total=3.0, as_of=TRADE_DATE),
        Earnings(period="2026-09-30", net_profit_yoy=5.0),
    )


def _patch_sources(monkeypatch, calls=None):
    calls = calls if calls is not None else []
    macro, valuation, margin, earnings = _blocks()

    def counted(name, value):
        def fake(*args, **kwargs):
            calls.append(name)
            return value

        return fake

    monkeypatch.setattr("market.fundamentals.fetch_macro", counted("macro", macro))
    monkeypatch.setattr(
        "market.fundamentals.fetch_valuation", counted("valuation", valuation)
    )
    monkeypatch.setattr("market.fundamentals.fetch_margin", counted("margin", margin))
    monkeypatch.setattr(
        "market.fundamentals.fetch_earnings", counted("earnings", earnings)
    )
    return calls


def test_history_mode_makes_no_request(monkeypatch):
    calls = _patch_sources(monkeypatch)

    result = fetch_fundamentals(TRADE_DATE, False)

    assert result == Fundamentals(unavailable="历史模式不可用")
    assert calls == []


def test_latest_mode_fetches_all_four_blocks(monkeypatch):
    calls = _patch_sources(monkeypatch)
    macro, valuation, margin, earnings = _blocks()

    result = fetch_fundamentals(TRADE_DATE, True)

    assert calls == ["macro", "valuation", "margin", "earnings"]
    assert result == Fundamentals(
        macro=macro, valuation=valuation, margin=margin, earnings=earnings
    )


def test_one_block_failure_is_none_and_the_others_survive(monkeypatch):
    _patch_sources(monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError("csindex down")

    monkeypatch.setattr("market.fundamentals.fetch_valuation", boom)

    result = fetch_fundamentals(TRADE_DATE, True)

    assert result.valuation is None
    assert result.macro is not None
    assert result.margin is not None
    assert result.earnings is not None


def test_margin_attribute_error_is_degraded(monkeypatch):
    import akshare as ak

    monkeypatch.delattr(ak, "stock_margin_sse_js", raising=False)
    monkeypatch.delattr(ak, "stock_margin_szse_js", raising=False)

    margin = fetch_margin(TRADE_DATE)

    assert margin == Margin()


def test_official_columns_all_missing_do_not_mark_the_source_available(monkeypatch):
    import akshare as ak

    monkeypatch.setattr(
        ak,
        "stock_index_pe_lg",
        lambda symbol: pd.DataFrame(
            {
                "日期": pd.to_datetime(["2026-11-01"]),
                "滚动市盈率": [12.6],
            }
        ),
    )
    monkeypatch.setattr(
        ak,
        "index_value_csindex",
        lambda symbol: pd.DataFrame(
            {
                "日期": pd.to_datetime(["2026-11-25"]),
                "市盈率1": [None],
                "市盈率2": [None],
                "股息率1": [None],
                "股息率2": [None],
            }
        ),
    )

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.official_pe1 is None
    assert valuation.official_pe2 is None
    assert valuation.official_date is None
    assert valuation.source == "乐咕乐股（akshare）"


def test_official_zero_value_still_counts_as_a_usable_source(monkeypatch):
    import akshare as ak

    value = 0.0

    monkeypatch.setattr(
        ak,
        "stock_index_pe_lg",
        lambda symbol: (_ for _ in ()).throw(RuntimeError("legulegu down")),
    )
    monkeypatch.setattr(
        ak,
        "index_value_csindex",
        lambda symbol: pd.DataFrame(
            {
                "日期": pd.to_datetime(["2026-11-25"]),
                "市盈率1": [value],
                "市盈率2": [None],
                "股息率1": [None],
                "股息率2": [None],
            }
        ),
    )

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.official_pe1 == value
    assert valuation.source == "中证指数（akshare）"
