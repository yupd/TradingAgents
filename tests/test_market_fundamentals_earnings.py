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
                "股票代码": code,
                "最新公告日期": announced,
                "净利润-净利润": net_profit,
                "营业总收入-营业总收入": revenue,
            }
            for code, announced, net_profit, revenue in rows
        ]
    )


def _install(monkeypatch, current, prior):
    import akshare as ak

    def fake(date):
        if date == "20260930":
            return current
        if date == "20250930":
            return prior
        raise AssertionError(f"unexpected period {date}")

    monkeypatch.setattr(ak, "stock_yjbb_em", fake)


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


def test_total_sum_uses_prior_year_frame(monkeypatch):
    current = _yjbb(
        [
            ("A", pd.Timestamp("2026-10-20"), 100.0, 200.0),
            ("B", pd.Timestamp("2026-10-21"), 60.0, 120.0),
        ]
    )
    prior = _yjbb(
        [
            ("A", pd.Timestamp("2025-10-20"), 50.0, 160.0),
            ("B", pd.Timestamp("2025-10-21"), 50.0, 150.0),
        ]
    )
    _install(monkeypatch, current, prior)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.period == "2026-09-30"
    assert earnings.announcement_cutoff == TRADE_DATE
    assert earnings.net_profit_yoy == 60.0
    assert earnings.revenue_yoy == 3.23
    assert earnings.coverage == 1.0
    assert earnings.coverage_low is False
    assert earnings.source == EARNINGS_SOURCE
    assert earnings.note == EARNINGS_NOTE


def test_announcement_date_filter_and_coverage(monkeypatch):
    current = _yjbb(
        [
            ("A", pd.Timestamp("2026-10-20"), 100.0, 200.0),
            ("B", pd.Timestamp("2026-11-30"), 500.0, 900.0),
            ("C", pd.NaT, 700.0, 700.0),
        ]
    )
    prior = _yjbb(
        [
            ("A", pd.Timestamp("2025-10-20"), 50.0, 160.0),
            ("B", pd.Timestamp("2025-10-20"), 50.0, 150.0),
            ("C", pd.Timestamp("2025-10-20"), 50.0, 150.0),
        ]
    )
    _install(monkeypatch, current, prior)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.covered == 1
    assert earnings.total == 3
    assert earnings.coverage == pytest.approx(1 / 3)
    assert earnings.coverage_low is True
    # Only the announced company A is aggregated.
    assert earnings.net_profit_yoy == 100.0
    assert earnings.revenue_yoy == 25.0


def test_missing_prior_code_is_excluded_from_both_sums(monkeypatch):
    current = _yjbb(
        [
            ("A", pd.Timestamp("2026-10-20"), 100.0, 200.0),
            ("B", pd.Timestamp("2026-10-21"), 60.0, 120.0),
        ]
    )
    prior = _yjbb(
        [
            ("A", pd.Timestamp("2025-10-20"), 50.0, 160.0),
        ]
    )
    _install(monkeypatch, current, prior)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.net_profit_yoy == 100.0
    assert earnings.revenue_yoy == 25.0


def test_non_positive_prior_total_yields_none(monkeypatch):
    current = _yjbb(
        [
            ("A", pd.Timestamp("2026-10-20"), 100.0, 200.0),
            ("B", pd.Timestamp("2026-10-21"), 60.0, 120.0),
        ]
    )
    prior = _yjbb(
        [
            ("A", pd.Timestamp("2025-10-20"), -100.0, 160.0),
            ("B", pd.Timestamp("2025-10-21"), 50.0, 150.0),
        ]
    )
    _install(monkeypatch, current, prior)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings.net_profit_yoy is None
    assert earnings.revenue_yoy == 3.23


def test_prior_fetch_failure_keeps_coverage(monkeypatch):
    current = _yjbb([("A", pd.Timestamp("2026-10-20"), 100.0, 200.0)])
    import akshare as ak

    def fake(date):
        if date == "20260930":
            return current
        raise RuntimeError("prior year down")

    monkeypatch.setattr(ak, "stock_yjbb_em", fake)

    earnings = fetch_earnings(TRADE_DATE)

    assert earnings is not None
    assert earnings.coverage == 1.0
    assert earnings.net_profit_yoy is None
    assert earnings.revenue_yoy is None


def test_empty_current_returns_none_without_prior_call(monkeypatch):
    calls = []
    import akshare as ak

    monkeypatch.setattr(
        ak, "stock_yjbb_em", lambda date: calls.append(date) or pd.DataFrame()
    )

    assert fetch_earnings("2026-11-27") is None
    assert calls == ["20260930"]


def test_requests_both_periods(monkeypatch):
    calls = []
    current = _yjbb([("A", pd.Timestamp("2026-10-20"), 100.0, 200.0)])
    prior = _yjbb([("A", pd.Timestamp("2025-10-20"), 50.0, 160.0)])
    import akshare as ak

    def fake(date):
        calls.append(date)
        return current if date == "20260930" else prior

    monkeypatch.setattr(ak, "stock_yjbb_em", fake)

    assert fetch_earnings("2026-11-27").net_profit_yoy == 100.0
    assert calls == ["20260930", "20250930"]


def test_interface_failure_returns_none(monkeypatch):
    def boom(date):
        raise RuntimeError("eastmoney down")

    import akshare as ak

    monkeypatch.setattr(ak, "stock_yjbb_em", boom)

    assert fetch_earnings(TRADE_DATE) is None
