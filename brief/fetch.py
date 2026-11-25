"""Collect one stock's brief facts; a failed source is recorded, not fatal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from tradingagents.dataflows.vendors.a_share.news import get_news
from tradingagents.dataflows.vendors.a_share.quotes import get_daily_bars, get_snapshot
from tradingagents.dataflows.vendors.a_share.signals import get_fund_flow, get_lockup_expiry
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare
from tradingagents.dataflows.vendors.a_share.types import DailyBar, Snapshot

from .watchlist import WatchItem


@dataclass
class StockFacts:
    code: str
    name: str = ""
    symbol: object | None = None
    quote: Snapshot | None = None
    bars: list[DailyBar] = field(default_factory=list)
    announcements: list[str] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)
    fund_flow: str = ""
    lockup: str = ""
    missing: list[str] = field(default_factory=list)


def _start_date(trade_date: str, days: int = 90) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")


def _is_sentinel(text: str) -> bool:
    return (text or "").startswith(("NO_DATA_AVAILABLE", "DATA_UNAVAILABLE"))


def _snapshot_from_bars(sym, bars: list[DailyBar]) -> Snapshot | None:
    """A historical quote built from closes, never from the live feed."""
    if not bars:
        return None
    last = bars[-1]
    prev = bars[-2].close if len(bars) > 1 else last.open
    change = ((last.close / prev) - 1) * 100 if prev else 0.0
    return Snapshot(code=sym.code, name="", price=last.close, prev_close=prev,
                    change_pct=change, volume=last.volume, turnover_rate=None,
                    pe_ttm=None, pb=None, source=last.source, as_of=last.date)


def collect_facts(item: WatchItem, trade_date: str) -> StockFacts:
    sym = parse_ashare(item.code)
    facts = StockFacts(code=item.code, symbol=sym)
    start = _start_date(trade_date)
    try:
        facts.bars = get_daily_bars(sym, start, trade_date)
    except Exception:
        facts.missing.append("bars")
    historical = trade_date < datetime.now().strftime("%Y-%m-%d")
    if historical:
        facts.quote = _snapshot_from_bars(sym, facts.bars)
        if facts.quote is None:
            facts.missing.append("quote")
    else:
        try:
            facts.quote = get_snapshot(sym)
            facts.name = facts.quote.name
        except Exception:
            facts.missing.append("quote")
    try:
        news = get_news(item.code, start, trade_date)
        if _is_sentinel(news) or not news:
            facts.missing.append("news")
        else:
            facts.announcements.append(news)
    except Exception:
        facts.missing.append("news")
    try:
        facts.fund_flow = get_fund_flow(item.code, trade_date, include_history=True)
        if _is_sentinel(facts.fund_flow):
            facts.missing.append("fund_flow")
    except Exception:
        facts.missing.append("fund_flow")
    try:
        facts.lockup = get_lockup_expiry(item.code, trade_date)
        if _is_sentinel(facts.lockup):
            facts.missing.append("lockup")
    except Exception:
        facts.missing.append("lockup")
    if not facts.name:
        facts.name = item.code
    return facts
