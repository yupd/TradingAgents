from brief import fetch
from brief.watchlist import WatchItem


def test_collect_records_failures_without_raising(monkeypatch):
    monkeypatch.setattr(fetch, "get_snapshot", lambda sym: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(fetch, "get_daily_bars", lambda *a: [])
    monkeypatch.setattr(fetch, "get_news", lambda *a: "")
    monkeypatch.setattr(fetch, "get_fund_flow", lambda *a: "")
    monkeypatch.setattr(fetch, "get_lockup_expiry", lambda *a: "")
    facts = fetch.collect_facts(WatchItem(code="600519"), "2026-11-25")
    assert facts.code == "600519"
    assert "quote" in facts.missing
