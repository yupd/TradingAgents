import pandas as pd
import pytest

from market.fundamentals import (
    EARNINGS_NOTE,
    EARNINGS_SOURCE,
    fetch_earnings,
    latest_report_period,
)

TRADE_DATE = "2026-11-20"


def _yjbb(rows):
    return pd.DataFrame(
        [
            {
                "最新公告日期": announced,
                "净利润-净利润": net_profit,
                "净利润-同比增长": net_yoy,
                "营业总收入-营业总收入": revenue,
                "营业总收入-同比增长": revenue_yoy,
            }
            for announced, net_profit, net_yoy, revenue, revenue_yoy in rows
        ]
    )


def _install(monkeypatch, frame):
    import akshare as ak

    monkeypatch.setattr(ak, "stock_yjbb_em", lambda date: frame)


@pytest.mark.parametrize(
    ("trade_date", "expected"),
    [
        ("2026-01-15", "2025-12-31"),
        ("2026-04-01", "2026-03-31"),
        ("2026-03-31", "2026-03-31"),
        ("2026-11-27", "2026-09-30"),
        ("2026-12-31", "2026-12-31"),
    ],
)
def test_latest_report_period(trade_date, expected):
    assert latest_report_period(trade_date) == expected


def test_announcement_date_filter_and_coverage(monkeypatch):
    frame = _yjbb(
        [
            (pd.Timestamp("2026-10-20"), 100.0, 100.0, 200.0, 25.0),
            (pd.Timestamp("2026-11-30"), 500.0, 900.0, 900.0, 900.0),
            (pd.NaT, 700.0, 900.0, 700.0, 900.0),
        ]
    )
    _install(monkeypatch, frame)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.period == "2026-09-30"
    assert earnings.announcement_cutoff == TRADE_DATE
    assert earnings.covered == 1
    assert earnings.total == 3
    assert earnings.coverage == pytest.approx(1 / 3)
    assert earnings.coverage_low is True
    # The late and announcement-less rows are excluded from the aggregate.
    assert earnings.net_profit_yoy == 100.0
    assert earnings.revenue_yoy == 25.0
    assert earnings.source == EARNINGS_SOURCE
    assert earnings.note == EARNINGS_NOTE


def test_weighted_aggregate_uses_prior_year_implied_base(monkeypatch):
    frame = _yjbb(
        [
            (pd.Timestamp("2026-10-20"), 100.0, 100.0, 200.0, 25.0),
            (pd.Timestamp("2026-10-21"), 60.0, 20.0, 120.0, -20.0),
        ]
    )
    _install(monkeypatch, frame)

    earnings = fetch_earnings(TRADE_DATE)

    # net: 160 / (100/2 + 60/1.2) - 1 = 60%; revenue: 320 / (160 + 150) - 1.
    assert earnings.net_profit_yoy == 60.0
    assert earnings.revenue_yoy == 3.23
    assert earnings.coverage == 1.0
    assert earnings.coverage_low is False


def test_invalid_yoy_rows_are_excluded_from_both_sums(monkeypatch):
    frame = _yjbb(
        [
            (pd.Timestamp("2026-10-20"), 100.0, 100.0, 200.0, 25.0),
            (pd.Timestamp("2026-10-21"), 60.0, None, 120.0, float("nan")),
            (pd.Timestamp("2026-10-22"), 1000.0, -100.0, 1000.0, -100.0),
        ]
    )
    _install(monkeypatch, frame)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.net_profit_yoy == 100.0
    assert earnings.revenue_yoy == 25.0


def test_non_positive_denominator_yields_none(monkeypatch):
    frame = _yjbb(
        [
            (pd.Timestamp("2026-10-20"), -100.0, 10.0, 100.0, 10.0),
            (pd.Timestamp("2026-10-21"), -50.0, 0.0, 50.0, 0.0),
        ]
    )
    _install(monkeypatch, frame)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.net_profit_yoy is None
    assert earnings.revenue_yoy == pytest.approx(6.45)


def test_coverage_at_eighty_percent_is_not_low(monkeypatch):
    frame = _yjbb(
        [
            (pd.Timestamp("2026-10-20"), 10.0, 10.0, 10.0, 10.0),
            (pd.Timestamp("2026-10-21"), 10.0, 10.0, 10.0, 10.0),
            (pd.Timestamp("2026-10-22"), 10.0, 10.0, 10.0, 10.0),
            (pd.Timestamp("2026-10-23"), 10.0, 10.0, 10.0, 10.0),
            (pd.Timestamp("2026-11-30"), 10.0, 10.0, 10.0, 10.0),
        ]
    )
    _install(monkeypatch, frame)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.covered == 4
    assert earnings.coverage == pytest.approx(0.8)
    assert earnings.coverage_low is False


def test_no_rows_announced_by_trade_date_still_reports_coverage(monkeypatch):
    frame = _yjbb([(pd.Timestamp("2026-11-30"), 10.0, 10.0, 10.0, 10.0)])
    _install(monkeypatch, frame)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.covered == 0
    assert earnings.coverage == 0.0
    assert earnings.coverage_low is True
    assert earnings.net_profit_yoy is None
    assert earnings.revenue_yoy is None


def test_requests_latest_report_period(monkeypatch):
    calls = []
    import akshare as ak

    monkeypatch.setattr(
        ak, "stock_yjbb_em", lambda date: calls.append(date) or pd.DataFrame()
    )

    assert fetch_earnings("2026-11-27") is None
    assert calls == ["20260930"]


def test_interface_failure_returns_none(monkeypatch):
    def boom(date):
        raise RuntimeError("eastmoney down")

    import akshare as ak

    monkeypatch.setattr(ak, "stock_yjbb_em", boom)

    assert fetch_earnings(TRADE_DATE) is None


def test_empty_table_returns_none(monkeypatch):
    _install(monkeypatch, pd.DataFrame())

    assert fetch_earnings(TRADE_DATE) is None
