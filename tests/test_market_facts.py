from market.fetch import IndexQuote, MarketFacts, Sentiment, Turnover


def test_empty_market_facts_has_no_optional_groups():
    facts = MarketFacts(trade_date="2026-11-26")
    assert facts.requested_date is None
    assert facts.as_of is None
    assert facts.turnover is None
    assert facts.sentiment is None
    assert facts.industries is None
    assert facts.trend is None
    assert facts.indices == []
    assert facts.news == []
    assert facts.gaps == []
    assert facts.sources == []


def test_index_quote_requires_identity_only():
    quote = IndexQuote(name="上证指数", code="000001")
    assert quote.close is None
    assert quote.change_pct is None
    assert quote.return_5d is None
    assert quote.return_20d is None
    assert quote.return_60d is None
    assert quote.ma20 is None
    assert quote.ma60 is None
    assert quote.volume_ratio is None
    assert quote.source is None
    assert quote.as_of is None


def test_turnover_and_sentiment_are_all_optional():
    turnover = Turnover()
    assert turnover.sh is None and turnover.total is None and turnover.note is None
    sentiment = Sentiment()
    assert sentiment.limit_up is None and sentiment.broken_rate is None
