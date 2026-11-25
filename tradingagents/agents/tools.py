"""The data tools the analysts call.

Each dated tool takes the run's ``trade_date`` from graph state (``InjectedState``)
and never serves data past it, whatever date the model asks for.
"""

from typing import Annotated, Literal

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tradingagents.dataflows.date_window import as_of, as_of_window, is_historical
from tradingagents.dataflows.errors import NoMarketDataError, VendorUnavailableError
from tradingagents.dataflows.router import no_data_available, route_to_vendor, vendor_unavailable


@tool
def get_stock_data(
    symbol: Annotated[str, InjectedState("company_of_interest")],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve stock price data (OHLCV) for the instrument under analysis.
    Uses the configured core_stock_apis vendor.
    Args:
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the price data for the instrument over the date range.
    """
    try:
        start_date, end_date = as_of_window(start_date, end_date, trade_date)
    except ValueError as e:
        return str(e)
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)


@tool
def get_indicators(
    symbol: Annotated[str, InjectedState("company_of_interest")],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve a single technical indicator for the instrument under analysis.
    Uses the configured technical_indicators vendor.
    Args:
        indicator (str): A single technical indicator name, e.g. 'rsi', 'macd'. Call this tool once per indicator.
        curr_date (str): The current trading date you are trading on, YYYY-mm-dd
        look_back_days (int): How many days to look back, default is 30
    Returns:
        str: A formatted dataframe containing the technical indicators for the instrument and indicator.
    """
    # LLMs sometimes pass multiple indicators as a comma-separated string;
    # split and process each individually.
    curr_date = as_of(curr_date, trade_date)
    indicators = [i.strip().lower() for i in indicator.split(",") if i.strip()]
    results = []
    for ind in indicators:
        try:
            results.append(route_to_vendor("get_indicators", symbol, ind, curr_date, look_back_days))
        except ValueError as e:
            results.append(str(e))
    return "\n\n".join(results)


@tool
def get_verified_market_snapshot(
    symbol: Annotated[str, InjectedState("company_of_interest")],
    curr_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[
        int, "number of recent trading rows to include for sanity-checking"
    ] = 30,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Deterministic verification snapshot for exact market-data claims.

    Returns the latest OHLCV row on or before curr_date, common technical
    indicators, and recent closes. Call this before making exact claims about
    price levels, Bollinger bands, RSI, MACD, moving averages, support /
    resistance, or historical comparisons, and treat it as the source of truth.
    """
    # An exception out of a tool would end the run.
    try:
        return route_to_vendor("get_verified_market_snapshot", symbol, as_of(curr_date, trade_date), look_back_days)
    except VendorUnavailableError as exc:
        return vendor_unavailable("get_verified_market_snapshot", exc)
    except NoMarketDataError as exc:
        return no_data_available(exc)


@tool
def get_fundamentals(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve comprehensive fundamental data for the instrument under analysis.
    Uses the configured fundamental_data vendor.
    Args:
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing comprehensive fundamental data
    """
    return route_to_vendor("get_fundamentals", ticker, as_of(curr_date, trade_date))


@tool
def get_balance_sheet(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    freq: Annotated[Literal["annual", "quarterly"], "reporting frequency"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve balance sheet data for the instrument under analysis.
    Uses the configured fundamental_data vendor.
    Args:
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing balance sheet data
    """
    return route_to_vendor("get_balance_sheet", ticker, freq, as_of(curr_date, trade_date))


@tool
def get_cashflow(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    freq: Annotated[Literal["annual", "quarterly"], "reporting frequency"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve cash flow statement data for the instrument under analysis.
    Uses the configured fundamental_data vendor.
    Args:
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing cash flow statement data
    """
    return route_to_vendor("get_cashflow", ticker, freq, as_of(curr_date, trade_date))


@tool
def get_income_statement(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    freq: Annotated[Literal["annual", "quarterly"], "reporting frequency"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve income statement data for the instrument under analysis.
    Uses the configured fundamental_data vendor.
    Args:
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing income statement data
    """
    return route_to_vendor("get_income_statement", ticker, freq, as_of(curr_date, trade_date))


@tool
def get_news(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve news data for the instrument under analysis.
    Uses the configured news_data vendor.
    Args:
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data
    """
    try:
        start_date, end_date = as_of_window(start_date, end_date, trade_date)
    except ValueError as e:
        return str(e)
    return route_to_vendor("get_news", ticker, start_date, end_date)


@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int | None, "Days to look back; omit to use the configured default"] = None,
    limit: Annotated[int | None, "Max articles to return; omit to use the configured default"] = None,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve global news data.
    Uses the configured news_data vendor. Defaults for look_back_days and
    limit come from DEFAULT_CONFIG (global_news_lookback_days,
    global_news_article_limit); pass explicit values to override.

    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back; omit to inherit config
        limit (int): Maximum number of articles to return; omit to inherit config

    Returns:
        str: A formatted string containing global news data
    """
    return route_to_vendor("get_global_news", as_of(curr_date, trade_date), look_back_days, limit)


@tool
def get_insider_transactions(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """
    Retrieve insider transaction information about a company.
    Uses the configured news_data vendor.
    Returns:
        str: A report of insider transaction data
    """
    return route_to_vendor("get_insider_transactions", ticker, trade_date or None)


@tool
def get_profit_forecast(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Consensus EPS forecast and coverage for an A-share, with a look-ahead warning on past runs."""
    return route_to_vendor("get_profit_forecast", ticker, as_of(curr_date, trade_date))


@tool
def get_hot_stocks(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format; empty for today"] = "",
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Today's hottest A-shares; only the current ranking exists, so past dates are refused."""
    if is_historical(trade_date):
        return f"历史日期不提供实时快照：热门榜只有当前版本（请求日 {trade_date}）"
    return route_to_vendor("get_hot_stocks", as_of(curr_date, trade_date))


@tool
def get_concept_blocks(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """The industry, concept and region blocks an A-share belongs to."""
    if is_historical(trade_date):
        return f"历史日期不提供实时快照：板块归属只有当前版本（请求日 {trade_date}）"
    return route_to_vendor("get_concept_blocks", ticker)


@tool
def get_fund_flow(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    include_history: Annotated[bool, "Include the last 20 sessions"] = True,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Main-force versus retail fund flow for an A-share, daily or over 20 sessions."""
    return route_to_vendor("get_fund_flow", ticker, as_of(curr_date, trade_date), include_history)


@tool
def get_northbound_flow(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    include_history: Annotated[bool, "Include the last 20 sessions"] = False,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Northbound (沪深股通) net buying."""
    return route_to_vendor("get_northbound_flow", as_of(curr_date, trade_date), include_history)


@tool
def get_dragon_tiger_board(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Days to look back"] = 30,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Dragon-tiger board appearances, seats and net buying for an A-share."""
    return route_to_vendor("get_dragon_tiger_board", ticker, as_of(curr_date, trade_date), look_back_days)


@tool
def get_lockup_expiry(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    forward_days: Annotated[int, "Days forward to check"] = 90,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Upcoming lockup expiries for an A-share."""
    return route_to_vendor("get_lockup_expiry", ticker, as_of(curr_date, trade_date), forward_days)


@tool
def get_industry_comparison(
    ticker: Annotated[str, InjectedState("company_of_interest")],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    top_n: Annotated[int, "How many industries to list"] = 20,
    trade_date: Annotated[str, InjectedState("trade_date")] = "",
) -> str:
    """Industry performance ranking for sector-rotation context."""
    return route_to_vendor("get_industry_comparison", ticker, as_of(curr_date, trade_date), top_n)
