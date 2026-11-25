from datetime import date

from tradingagents.dataflows.vendors.a_share import calendar as cal


def test_previous_trade_date_skips_holiday(monkeypatch):
    monkeypatch.setattr(cal, "_load_dates", lambda: (date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 9)))
    assert cal.previous_trade_date("2026-10-02") == "2026-09-30"
    assert cal.is_trade_date("2026-09-30") is True
    assert cal.is_trade_date("2026-10-02") is False


def test_previous_trade_date_on_a_trade_date_returns_itself(monkeypatch):
    monkeypatch.setattr(cal, "_load_dates", lambda: (date(2026, 9, 29), date(2026, 9, 30)))
    assert cal.previous_trade_date("2026-09-30") == "2026-09-30"


def test_uses_the_renamed_calendar_api():
    import pandas as pd

    class FakeAk:
        @staticmethod
        def calendar_trade_date_hist_sina():
            return pd.DataFrame({"trade_date": ["2026-01-05"]})

    assert cal._fetch_calendar(FakeAk()).iloc[0]["trade_date"] == "2026-01-05"


def test_falls_back_to_the_old_calendar_name():
    import pandas as pd

    class FakeAk:
        @staticmethod
        def tool_trade_date_hist_sina():
            return pd.DataFrame({"trade_date": ["2026-01-05"]})

    assert cal._fetch_calendar(FakeAk()).iloc[0]["trade_date"] == "2026-01-05"
