import pytest

from tradingagents.agents.rating import extract_rating


@pytest.mark.parametrize("text,expected", [
    ("评级：买入", "Buy"),
    ("最终评级 **增持**", "Overweight"),
    ("Rating: Hold", "Hold"),
    ("给予减持评级", "Underweight"),
    ("目标价 18 元", None),
])
def test_chinese_rating(text, expected):
    assert extract_rating(text) == expected


def test_rating_line_wins_over_consensus():
    assert extract_rating("Consensus rating: Buy\n\nOur rating: 卖出") == "Sell"
