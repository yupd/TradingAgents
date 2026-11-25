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


def test_historical_brief_uses_bars_not_live(monkeypatch):
    from tradingagents.dataflows.vendors.a_share.types import DailyBar

    bars = [DailyBar(date="2026-05-29", open=9.0, high=9.5, low=8.9, close=9.0, volume=1000,
                     source="mootdx", as_of="2026-05-29"),
            DailyBar(date="2026-06-01", open=9.0, high=9.5, low=8.9, close=9.2, volume=1100,
                     source="mootdx", as_of="2026-06-01")]
    monkeypatch.setattr(fetch, "get_snapshot", lambda sym: (_ for _ in ()).throw(AssertionError("live used")))
    monkeypatch.setattr(fetch, "get_daily_bars", lambda *a: bars)
    monkeypatch.setattr(fetch, "get_news", lambda *a: "")
    monkeypatch.setattr(fetch, "get_fund_flow", lambda *a: "")
    monkeypatch.setattr(fetch, "get_lockup_expiry", lambda *a: "")
    facts = fetch.collect_facts(WatchItem(code="600519"), "2026-06-01")
    assert facts.quote is not None
    assert facts.quote.source == "mootdx" and facts.quote.as_of == "2026-06-01"


def test_sentinel_marks_the_field_missing(monkeypatch):
    monkeypatch.setattr(fetch, "get_snapshot", lambda sym: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(fetch, "get_daily_bars", lambda *a: [])
    monkeypatch.setattr(fetch, "get_news", lambda *a: "DATA_UNAVAILABLE: no news")
    monkeypatch.setattr(fetch, "get_fund_flow", lambda *a: "DATA_UNAVAILABLE: no flow")
    monkeypatch.setattr(fetch, "get_lockup_expiry", lambda *a: "NO_DATA_AVAILABLE: none")
    facts = fetch.collect_facts(WatchItem(code="600519"), "2026-11-25")
    assert {"news", "fund_flow", "lockup"} <= set(facts.missing)
