from tradingagents.reporting import _header


def test_header_has_provenance():
    settings = {"llm_provider": "deepseek", "deep_think_llm": "deepseek-v4-pro",
                "data_as_of": "2026-11-25"}
    text = _header("600519", {"final_trade_decision": "Rating: 买入"}, settings)
    assert "Model: deepseek-v4-pro" in text
    assert "Provider: deepseek" in text
    assert "Data as of: 2026-11-25" in text
    assert "Memory log" not in text


def test_html_details_include_data_as_of():
    from tradingagents.report_html import _run_details

    details = dict(_run_details({}, {"llm_provider": "deepseek", "data_as_of": "2026-11-25"}))
    assert "Data as of" in details and "2026-11-25" in details["Data as of"]
