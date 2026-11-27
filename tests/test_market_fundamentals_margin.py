import pandas as pd
import pytest

from market.fundamentals import MARGIN_SOURCE, Margin, fetch_margin

TRADE_DATE = "2026-11-27"


def _frame(dates, values):
    return pd.DataFrame(
        {"日期": pd.to_datetime(dates), "融资融券余额": [value * 1e8 for value in values]}
    )


def _install(monkeypatch, sh, sz):
    import akshare as ak

    monkeypatch.setattr(ak, "stock_margin_sse_js", sh)
    monkeypatch.setattr(ak, "stock_margin_szse_js", sz)


def _days(count):
    return pd.bdate_range(end="2026-11-25", periods=count).strftime("%Y-%m-%d")


def test_common_dates_align_and_sum(monkeypatch):
    dates = _days(7)
    _install(
        monkeypatch,
        lambda: _frame(dates, [100, 101, 102, 103, 104, 105, 106]),
        lambda: _frame(dates, [50, 51, 52, 53, 54, 55, 56]),
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.as_of == "2026-11-25"
    assert margin.sh == 106.0
    assert margin.sz == 56.0
    assert margin.total == 162.0
    assert margin.change_5d == 10.0
    assert margin.source == MARGIN_SOURCE
    assert margin.note is None


def test_five_day_change_needs_six_common_dates(monkeypatch):
    dates = _days(5)
    _install(
        monkeypatch,
        lambda: _frame(dates, [102, 103, 104, 105, 106]),
        lambda: _frame(dates, [52, 53, 54, 55, 56]),
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.total == 162.0
    assert margin.change_5d is None


def test_single_market_degrades_to_no_total(monkeypatch):
    dates = _days(7)
    _install(
        monkeypatch,
        lambda: _frame(dates, [100, 101, 102, 103, 104, 105, 106]),
        lambda: pd.DataFrame(),
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.sh == 106.0
    assert margin.sz is None
    assert margin.total is None
    assert margin.change_5d is None
    assert margin.as_of == "2026-11-25"
    assert "仅沪市" in margin.note
    assert margin.source == "上交所（akshare）"


def test_rows_after_trade_date_and_nan_are_ignored(monkeypatch):
    dates = ["2026-11-24", "2026-11-25", "2026-11-30"]
    _install(
        monkeypatch,
        lambda: _frame(dates, [100, 101, 999]),
        lambda: pd.DataFrame(
            {
                "日期": pd.to_datetime(["2026-11-25"]),
                "融资融券余额": [float("nan")],
            }
        ),
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.sh == 101.0
    assert margin.sz is None
    assert margin.total is None
    assert margin.as_of == "2026-11-25"


def test_both_sources_failing_returns_empty_margin(monkeypatch):
    def boom():
        raise RuntimeError("down")

    _install(monkeypatch, boom, boom)

    margin = fetch_margin(TRADE_DATE)

    assert margin == Margin()
    assert margin.source is None


def test_missing_column_degrades_quietly(monkeypatch):
    _install(
        monkeypatch,
        lambda: pd.DataFrame({"日期": pd.to_datetime(["2026-11-25"]), "余额": [1e8]}),
        lambda: pd.DataFrame(),
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.total is None
    assert margin.as_of is None
    assert margin.note is None


def test_both_sides_without_shared_date_report_one_side(monkeypatch):
    _install(
        monkeypatch,
        lambda: _frame(["2026-11-24"], [100]),
        lambda: _frame(["2026-11-25"], [50]),
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.sh is None
    assert margin.sz == 50.0
    assert margin.total is None
    assert margin.change_5d is None
    assert margin.as_of == "2026-11-25"
    assert "无共同日期" in margin.note
