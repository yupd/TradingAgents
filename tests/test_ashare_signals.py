import tradingagents.dataflows.vendors.a_share.signals as s


def test_fund_flow_history_excludes_same_day_after_close(monkeypatch):
    monkeypatch.setattr(s, "_fetch_fund_flow",
                        lambda *a: [{"date": "2026-06-01", "main_net": 1.2e8}])
    text = s.get_fund_flow("600519", "2026-06-01", include_history=False)
    assert text.startswith("NO_DATA_AVAILABLE")


def test_fund_flow_live_includes_same_day(monkeypatch):
    monkeypatch.setattr(s, "_today", lambda: "2026-06-01")
    monkeypatch.setattr(s, "_fetch_fund_flow",
                        lambda *a: [{"date": "2026-06-01", "main_net": 1.2e8}])
    text = s.get_fund_flow("600519", "2026-06-01", include_history=False)
    assert "2026-06-01" in text and "实时" not in text


def test_dragon_tiger_excludes_same_day_history(monkeypatch):
    monkeypatch.setattr(s, "_fetch_lhb",
                        lambda *a: [{"date": "2026-06-01", "seat": "机构专用", "net": 3.0e7}])
    text = s.get_dragon_tiger_board("600519", "2026-06-01")
    assert text.startswith("NO_DATA_AVAILABLE")


def test_dragon_tiger_lists_seats(monkeypatch):
    monkeypatch.setattr(s, "_fetch_lhb",
                        lambda *a: [{"date": "2026-05-28", "seat": "机构专用", "net": 3.0e7}])
    text = s.get_dragon_tiger_board("600519", "2026-06-01")
    assert "机构专用" in text and "2026-05-28" in text


def test_signal_failure_degrades(monkeypatch):
    monkeypatch.setattr(s, "_fetch_lhb", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    text = s.get_dragon_tiger_board("600519", "2026-06-01")
    assert "DATA_UNAVAILABLE" in text
