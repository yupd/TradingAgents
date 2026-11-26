import tradingagents.dataflows.vendors.a_share.signals as s


def test_lockup_filters_announced_after_as_of(monkeypatch):
    rows = [{"announced": "2026-05-01", "expiry": "2026-07-01", "ratio": 3.2},
            {"announced": "2026-06-10", "expiry": "2026-08-01", "ratio": 1.0}]
    monkeypatch.setattr(s, "_fetch_lockups", lambda *a: rows)
    text = s.get_lockup_expiry("600519", "2026-06-01")
    assert "2026-07-01" in text and "2026-08-01" not in text


def test_forecast_flags_historical_snapshot(monkeypatch):
    monkeypatch.setattr(s, "_fetch_forecast", lambda *a: {"eps": 5.2, "coverage": 12})
    text = s.get_profit_forecast("600519", "2026-06-01")
    assert "current snapshot, not historical" in text


def test_insider_uses_ashare_wording(monkeypatch):
    monkeypatch.setattr(s, "_fetch_holders", lambda *a: [{"date": "2026-05-01", "name": "某某", "change": -1.2}])
    text = s.get_insider_transactions("600519")
    assert "减持" in text


def test_northbound_nan_is_reported_not_printed(monkeypatch):
    import pandas as pd
    import akshare as ak
    import tradingagents.dataflows.vendors.a_share.signals as s

    frame = pd.DataFrame({"日期": ["2026-11-25"], "当日成交净买额": [float("nan")]})
    monkeypatch.setattr(ak, "stock_hsgt_hist_em", lambda **k: frame)
    text = s.get_northbound_flow("2026-11-25")
    assert text.startswith("NO_DATA_AVAILABLE") and "NaN" not in text


def test_forecast_parses_ths_columns(monkeypatch):
    import pandas as pd
    import akshare as ak
    import tradingagents.dataflows.vendors.a_share.signals as s
    from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

    frame = pd.DataFrame({"年度": ["2026"], "预测机构数": [44], "均值": [66.85]})
    monkeypatch.setattr(ak, "stock_profit_forecast_ths", lambda **k: frame)
    data = s._fetch_forecast(parse_ashare("600519"))
    assert data == {"year": "2026", "eps": 66.85, "coverage": 44}


def test_industry_parses_ths_columns(monkeypatch):
    import pandas as pd
    import akshare as ak
    import tradingagents.dataflows.vendors.a_share.signals as s
    from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

    frame = pd.DataFrame({"板块": ["白酒"], "涨跌幅": [1.2]})
    monkeypatch.setattr(ak, "stock_board_industry_summary_ths", lambda: frame)
    rows = s._fetch_industry(parse_ashare("600519"), 20)
    assert rows == [{"name": "白酒", "change": 1.2}]
