from cli.display import ANALYST_AGENT_NAMES, ANALYST_ORDER


def test_status_order_covers_seven_analysts():
    assert ANALYST_ORDER == ["market", "social", "news", "fundamentals",
                             "policy", "hot_money", "lockup"]
    assert {"Policy Analyst", "Hot Money Analyst", "Lockup Analyst"} <= set(ANALYST_AGENT_NAMES.values())
