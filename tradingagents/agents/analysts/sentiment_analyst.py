"""Sentiment analyst: one sentiment report from three sources.

The node fetches its sources before calling the model and puts them in the
prompt, so the model reports on data it was given rather than inventing posts:

  1. News headlines: Yahoo Finance
  2. StockTwits messages: the cashtag stream, with Bullish/Bearish tags
  3. Reddit posts: r/wallstreetbets, r/stocks, r/investing, or crypto communities for a crypto pair

Each source is trimmed to the analysis window. With a TypeSafe key, the social
posts are screened by Jev first (see post_screen). These feeds serve recent items
and are not archived, so a historical run's sentiment inputs are not
point-in-time.

The report is a SentimentReport through structured output where the provider
supports it and free text otherwise, so the band, score and confidence header
reads the same across providers.
"""

from datetime import datetime, timedelta

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.schemas import SentimentReport, render_sentiment_report
from tradingagents.agents.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)
from tradingagents.agents.tools import get_fund_flow, get_hot_stocks, get_news, get_stock_data
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def create_sentiment_analyst(llm):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches news + StockTwits + Reddit data, injects them into the
    prompt as structured blocks, and produces a deterministic sentiment
    report via structured output (with a free-text fallback for providers
    that do not support it).
    """
    structured_llm = bind_structured(llm, SentimentReport, "Sentiment Analyst")

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = get_instrument_context_from_state(state)

        # Pre-fetch every source; each fetcher degrades to a placeholder string,
        # so the LLM always sees something real or an explicit gap.
        news_block = get_news.func(ticker, start_date, end_date)
        try:
            parse_ashare(ticker)
            is_cn = True
        except ValueError:
            is_cn = False
        if is_cn:
            system_message = build_ashare_system_message(
                news_block=news_block,
                flow_block=get_fund_flow.func(ticker, end_date, True),
                hot_block=get_hot_stocks.func(end_date),
                price_block=get_stock_data.func(ticker, start_date, end_date),
            )
        else:
            system_message = _build_system_message(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                news_block=news_block,
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Report what your tools support; another agent decides the trade."
                    # No tool-calling here: the data is pre-fetched into the
                    # prompt, so tool-range wording would only invite a
                    # hallucinated tool call (#1130).
                    " Today's date is {current_date}; treat it as 'now' for all analysis. {instrument_context}"
                    " " + NO_EXTERNAL_TOOLS +
                    "\n{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # Format the template into a concrete message list so the structured
        # and free-text paths receive the same input. No bind_tools — the
        # data is already in the prompt.
        formatted_messages = prompt.format_messages(messages=state["messages"])

        report_text = invoke_structured_or_freetext(
            structured_llm,
            llm,
            formatted_messages,
            render_sentiment_report,
            "Sentiment Analyst",
        )

        return {
            "messages": [AIMessage(content=report_text)],
            "sentiment_report": report_text,
        }

    return sentiment_analyst_node


def _build_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
) -> str:
    """Assemble the sentiment-analyst system message from its prefetched source."""
    return f"""You are a financial market sentiment analyst. Your task is to produce a comprehensive sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on the news headlines that have already been collected for you.

## Data source (pre-fetched, in this prompt)

### News headlines — past 7 days
Institutional framing. Fact-driven, slower-moving signal.

<start_of_news>
{news_block}
<end_of_news>

## How to analyze this data

1. **Separate event from opinion.** A headline is an event; commentary in it is opinion. Weight them differently.
2. **Identify recurring narrative themes.** What topic keeps coming up? That is the dominant narrative.
3. **Be honest about data limits.** If the source returned an "<unavailable>" placeholder or only a few items, say so in `confidence` and the narrative.
4. **Past sentiment is not predictive.** Frame conclusions as signal to weigh alongside fundamentals and technicals.

## Output fields

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish.
- **overall_score**: A number from 0 (maximally bearish) to 10 (maximally bullish); 5 is neutral.
- **confidence**: low / medium / high, based on data quality and sample size.
- **narrative**: Source-by-source breakdown, dominant themes, catalysts and risks, and a markdown summary table.

{get_language_instruction()}"""


def build_ashare_system_message(*, news_block: str, flow_block: str,
                               hot_block: str, price_block: str) -> str:
    """The A-share sentiment prompt: hard signals first, news to explain them."""
    return f"""You are a financial market sentiment analyst for a mainland A-share. Produce a comprehensive sentiment report from four pre-fetched sources.

## Data sources (pre-fetched)

### Fund flow — the hardest evidence
Money moving is stronger evidence than words. Read main-force versus retail direction.

<start_of_fund_flow>
{flow_block}
<end_of_fund_flow>

### Hot-stock list — where retail attention is
<start_of_hot_stocks>
{hot_block}
<end_of_hot_stocks>

### Price and volume — the strength of the move
<start_of_price_volume>
{price_block}
<end_of_price_volume>

### News — what explains the sentiment
<start_of_news>
{news_block}
<end_of_news>

## How to analyze this data

1. **Fund flow first.** A rising price with main-force outflow is a warning; a falling price with main-force inflow may be accumulation. Say which divergence you see.
2. **Volume confirms or denies.** A move without volume expansion is weak.
3. **Retail attention is contrarian at extremes.** Very high attention with accelerating price can mark a near-term top; low attention with improving flow can mark a bottom.
4. **News explains, it does not replace the hard data.** If the news is bullish but flow is negative, say so.
5. **Be honest about data limits.** Any "<unavailable>" or "DATA_UNAVAILABLE" block lowers confidence; say so.

## Output fields

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish.
- **overall_score**: 0 (maximally bearish) to 10 (maximally bullish); 5 is neutral.
- **confidence**: low / medium / high, based on data quality.
- **narrative**: Source-by-source breakdown, divergences, dominant narrative, catalysts and risks, plus a markdown summary table.

{get_language_instruction()}"""
