from web.pdf_export import generate_markdown


def test_markdown_uses_this_forks_keys_and_has_no_missing_data_warning():
    state = {
        "investment_plan": "研究经理计划",
        "trader_investment_plan": "交易员计划",
        "final_trade_decision": "评级: 买入",
        "final_rating": "Buy",
        "investment_debate_state": {"bull_history": "多方", "bear_history": "空方"},
        "risk_debate_state": {"aggressive_history": "激进", "conservative_history": "保守",
                              "neutral_history": "中性"},
    }
    md = generate_markdown(state, "600519", "2026-11-26", "Buy")
    assert "研究经理计划" in md
    assert "交易员计划" in md
    assert "评级: 买入" in md
    assert "数据缺失" not in md
    assert "缺" not in md
