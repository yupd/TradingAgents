"""Typed A-share values rendered as the strings the agent tools return."""

from __future__ import annotations

from .types import AStockSymbol, DailyBar, Snapshot


def _table(rows: list[list[object]], header: list[str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def format_bars(symbol: AStockSymbol, bars: list[DailyBar], title: str = "日线") -> str:
    source = bars[-1].source if bars else "unknown"
    through = bars[-1].date if bars else "unknown"
    rows = [[b.date, f"{b.open:.2f}", f"{b.high:.2f}", f"{b.low:.2f}",
             f"{b.close:.2f}", f"{b.volume:.0f}"] for b in bars]
    return (f"# {symbol.display} {title}\n\n"
            + _table(rows, ["Date", "Open", "High", "Low", "Close", "Volume"])
            + f"\n\nSource: {source} | As of: {through} | 单位：元、股")


def format_snapshot(symbol: AStockSymbol, snap: Snapshot) -> str:
    rows = [
        ["名称", snap.name],
        ["最新价", f"{snap.price:.2f}"],
        ["昨收", f"{snap.prev_close:.2f}"],
        ["涨跌幅", f"{snap.change_pct:.2f}%"],
        ["成交量", f"{snap.volume:.0f}"],
        ["换手率", "—" if snap.turnover_rate is None else f"{snap.turnover_rate:.2f}%"],
        ["市盈率(TTM)", "—" if snap.pe_ttm is None else f"{snap.pe_ttm:.2f}"],
        ["市净率", "—" if snap.pb is None else f"{snap.pb:.2f}"],
    ]
    return (f"# {symbol.display} 快照\n\n" + _table(rows, ["项", "值"])
            + f"\n\nSource: {snap.source} | As of: {snap.as_of}")
