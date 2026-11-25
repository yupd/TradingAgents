"""The user-maintained watchlist."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare


@dataclass(frozen=True)
class WatchItem:
    code: str
    notes: str = ""


def load_watchlist(path: Path) -> list[WatchItem]:
    # BaseLoader keeps codes as strings, so YAML does not turn 000001 into 1.
    data = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=yaml.BaseLoader) or {}
    stocks = data.get("stocks") or []
    items: list[WatchItem] = []
    seen: set[str] = set()
    for entry in stocks:
        raw = entry.get("code") if isinstance(entry, dict) else entry
        code = str(raw or "").strip()
        parse_ashare(code)                  # raises ValueError for non-A-share codes
        if code in seen:
            continue
        seen.add(code)
        notes = str(entry.get("notes") or "") if isinstance(entry, dict) else ""
        items.append(WatchItem(code=code, notes=notes))
    if not items:
        raise ValueError(f"watchlist has no stocks: {path}")
    return items
