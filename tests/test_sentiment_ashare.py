from tradingagents.agents.analysts.sentiment_analyst import build_ashare_system_message


def test_ashare_sentiment_blocks_cover_four_sources():
    text = build_ashare_system_message(news_block="NEWS", flow_block="FLOW",
                                       hot_block="HOT", price_block="PRICE")
    for block in ("NEWS", "FLOW", "HOT", "PRICE"):
        assert block in text
