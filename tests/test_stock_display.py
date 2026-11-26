from web.stock_display import (
    normalize_report_state_mentions,
    normalize_stock_mentions,
    stock_display_label,
)


def test_every_supported_code_spelling_normalizes_to_six_digits():
    assert stock_display_label("SH600519") == "600519"
    assert stock_display_label("600519.SS") == "600519"
    assert stock_display_label("600519.sh") == "600519"


def test_non_ashare_input_is_left_alone():
    assert stock_display_label("贵州茅台") == "贵州茅台"
    assert stock_display_label("0700.HK") == "0700.HK"


def test_name_comes_from_state_when_present():
    assert stock_display_label("600519", {"company_name": "贵州茅台"}) == "600519 贵州茅台"


def test_mentions_are_normalized_once():
    state = {"company_name": "贵州茅台"}
    assert normalize_stock_mentions("600519 上涨", "600519", state) == "600519 贵州茅台 上涨"
    assert normalize_stock_mentions("600519 贵州茅台 上涨", "600519", state) == "600519 贵州茅台 上涨"


def test_report_state_fields_are_normalized_in_place():
    state = {"company_name": "贵州茅台", "market_report": "600519 走强",
             "risk_debate_state": {"aggressive_history": "看多 600519"}}
    normalize_report_state_mentions(state, "600519")
    assert state["market_report"] == "600519 贵州茅台 走强"
    assert state["risk_debate_state"]["aggressive_history"] == "看多 600519 贵州茅台"
