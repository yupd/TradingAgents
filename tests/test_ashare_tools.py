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


def test_signal_tools_hide_trade_date_and_clamp(monkeypatch):
    from tradingagents.agents.tools import get_fund_flow

    props = get_fund_flow.tool_call_schema.model_json_schema()["properties"]
    assert "trade_date" not in props
    seen = {}
    monkeypatch.setattr("tradingagents.agents.tools.route_to_vendor",
                        lambda method, *args, **kwargs: seen.setdefault(method, args) or "ok")
    get_fund_flow.invoke({"ticker": "600519", "curr_date": "2026-12-31", "trade_date": "2026-06-01"})
    assert seen["get_fund_flow"][1] == "2026-06-01"


def test_kline_pattern_tool_routed(monkeypatch):
    from tradingagents.agents.tools import get_kline_patterns

    calls = {}

    def fake(method, *args, **kwargs):
        calls["method"] = method
        calls["args"] = args
        return "ok"

    monkeypatch.setattr("tradingagents.agents.tools.route_to_vendor", fake)
    out = get_kline_patterns.invoke(
        {"symbol": "600519", "curr_date": "2026-12-31", "trade_date": "2026-06-01"})
    assert out == "ok"
    assert calls["method"] == "get_kline_patterns"
    assert calls["args"] == ("600519", "2026-06-01", 60)
    props = get_kline_patterns.tool_call_schema.model_json_schema()["properties"]
    assert "trade_date" not in props


def test_kline_pattern_tool_unavailable_vendor(monkeypatch):
    from tradingagents.agents.tools import get_kline_patterns

    monkeypatch.setattr(
        "tradingagents.agents.tools.route_to_vendor",
        lambda *a, **k: (_ for _ in ()).throw(
            ValueError("Configured vendor(s) ['yfinance'] not available "
                       "for 'get_kline_patterns'")))
    out = get_kline_patterns.invoke({"symbol": "600519", "curr_date": "2026-06-01"})
    assert out.startswith("DATA_UNAVAILABLE")
    assert "未检测到" not in out
