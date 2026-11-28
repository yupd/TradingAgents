import pandas as pd
import pytest

from market.fundamentals import MARGIN_SOURCE, Margin, fetch_margin

TRADE_DATE = "2026-11-27"


def _frame(dates, values):
    return pd.DataFrame(
        {"日期": pd.to_datetime(dates), "融资融券余额": [value * 1e8 for value in values]}
    )


def _dated_sse(rows):
    """``信用交易日期`` is YYYYMMDD; values are yuan."""
    return pd.DataFrame(
        {
            "信用交易日期": [day.replace("-", "") for day, _ in rows],
            "融资融券余额": [value * 1e8 for _, value in rows],
        }
    )


def _dated_szse(value):
    """SZSE's dated endpoint returns one row in 亿元."""
    return pd.DataFrame({"融资融券余额": [value]})


def _install(monkeypatch, sh, sz, sse_dated=None, szse_dated=None):
    import akshare as ak

    monkeypatch.setattr(ak, "stock_margin_sse_js", sh)
    monkeypatch.setattr(ak, "stock_margin_szse_js", sz)
    monkeypatch.setattr(
        ak, "stock_margin_sse", sse_dated or (lambda **kwargs: pd.DataFrame())
    )
    monkeypatch.setattr(
        ak, "stock_margin_szse", szse_dated or (lambda **kwargs: pd.DataFrame())
    )


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
    assert margin.stale_days == 2


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


def test_stale_history_falls_back_to_dated(monkeypatch):
    stale = ["2026-11-04", "2026-11-05"]
    _install(
        monkeypatch,
        lambda: _frame(stale, [100, 101]),
        lambda: _frame(stale, [50, 51]),
        sse_dated=lambda **kwargs: _dated_sse([("2026-11-23", 12000.0)]),
        szse_dated=lambda **kwargs: _dated_szse(11000.0),
    )

    margin = fetch_margin(TRADE_DATE)

    # 深市有 11-27，沪市只到 11-23，两市无共同日期：只报较新的深市。
    assert margin.sh is None
    assert margin.sz == 11000.0
    assert margin.as_of == TRADE_DATE
    assert margin.stale_days == 0
    assert "无共同日期" in margin.note


def test_szse_dated_walks_back_to_previous_day(monkeypatch):
    stale = ["2026-11-04", "2026-11-05"]

    def szse_dated(**kwargs):
        if kwargs.get("date") == "20261127":
            return pd.DataFrame()
        return _dated_szse(11000.0)

    _install(
        monkeypatch,
        lambda: _frame(stale, [100, 101]),
        lambda: _frame(stale, [50, 51]),
        sse_dated=lambda **kwargs: _dated_sse([("2026-11-26", 12000.0)]),
        szse_dated=szse_dated,
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.sh == 12000.0
    assert margin.sz == 11000.0
    assert margin.total == 23000.0
    assert margin.as_of == "2026-11-26"
    assert margin.stale_days == 1
    assert margin.note is None


def test_stale_common_date_is_flagged(monkeypatch):
    stale = ["2026-11-04", "2026-11-05"]
    _install(
        monkeypatch,
        lambda: _frame(stale, [100, 101]),
        lambda: _frame(stale, [50, 51]),
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.as_of == "2026-11-05"
    assert margin.stale_days == 22
    assert "数据滞后 22 天" in margin.note


def test_fresh_history_skips_dated_endpoints(monkeypatch):
    dates = _days(7)

    def boom(**kwargs):
        raise AssertionError("dated endpoint should not be called")

    _install(
        monkeypatch,
        lambda: _frame(dates, [100, 101, 102, 103, 104, 105, 106]),
        lambda: _frame(dates, [50, 51, 52, 53, 54, 55, 56]),
        sse_dated=boom,
        szse_dated=boom,
    )

    margin = fetch_margin(TRADE_DATE)

    assert margin.as_of == "2026-11-25"
    assert margin.stale_days == 2
    assert margin.note is None
