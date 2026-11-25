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
