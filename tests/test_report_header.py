from tradingagents.reporting import _header


def test_header_has_provenance():
    settings = {"llm_provider": "deepseek", "deep_think_llm": "deepseek-v4-pro",
                "data_as_of": "2026-11-25"}
    text = _header("600519", {"final_trade_decision": "Rating: 买入"}, settings)
    assert "Model: deepseek-v4-pro" in text
    assert "Provider: deepseek" in text
    assert "Data as of: 2026-11-25" in text
    assert "Memory log" not in text
