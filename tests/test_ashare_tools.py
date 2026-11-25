from tradingagents.agents.tools import get_verified_market_snapshot


def test_snapshot_is_routed(monkeypatch):
    calls = {}

    def fake(method, *args, **kwargs):
        calls["method"] = method
        calls["args"] = args
        return "ok"

    monkeypatch.setattr("tradingagents.agents.tools.route_to_vendor", fake)
    out = get_verified_market_snapshot.invoke(
        {"symbol": "600519", "curr_date": "2026-06-01", "trade_date": "2026-06-01"})
    assert out == "ok"
    assert calls["method"] == "get_verified_market_snapshot"
    assert calls["args"] == ("600519", "2026-06-01", 30)
