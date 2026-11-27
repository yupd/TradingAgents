"""Market-wide fundamentals; each source degrades to ``None`` instead of failing."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SOURCE = "akshare 宏观接口（国家统计局口径）"
MONTH_RE = re.compile(r"(\d{4})年(\d{1,2})月")


@dataclass
class MacroItem:
    name: str
    value: float | None
    unit: str
    period: str | None
    source: str | None
    note: str | None = None


@dataclass
class MacroBlock:
    items: list[MacroItem]
    note: str | None = None


@dataclass
class Valuation:
    pe_ttm: float | None = None
    pe_percentile: float | None = None
    percentile_window: int | None = None
    pe_date: str | None = None
    official_pe1: float | None = None
    official_pe2: float | None = None
    official_div1: float | None = None
    official_div2: float | None = None
    official_date: str | None = None
    source: str | None = None
    note: str | None = None


@dataclass
class Margin:
    sh: float | None = None
    sz: float | None = None
    total: float | None = None
    change_5d: float | None = None
    as_of: str | None = None
    source: str | None = None
    note: str | None = None


@dataclass
class Earnings:
    period: str | None = None
    net_profit_yoy: float | None = None
    revenue_yoy: float | None = None
    coverage: float | None = None
    covered: int | None = None
    total: int | None = None
    coverage_low: bool = False
    source: str | None = None
    note: str | None = None


@dataclass
class Fundamentals:
    macro: MacroBlock | None = None
    valuation: Valuation | None = None
    margin: Margin | None = None
    earnings: Earnings | None = None
    unavailable: str | None = None


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number  # akshare uses NaN for missing


def _period_of(row):
    match = MONTH_RE.search(str(row.get("月份", "")))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _latest_row(frame):
    """Return the row with the newest 月份, regardless of row order."""
    if frame is None or getattr(frame, "empty", True) or "月份" not in frame.columns:
        return None
    best = None
    for index, row in frame.iterrows():
        key = _period_of(row)
        if key is not None and (best is None or key > best[0]):
            best = (key, index)
    return None if best is None else frame.loc[best[1]]


def _find_row(frame, year, month):
    for _, row in frame.iterrows():
        if _period_of(row) == (year, month):
            return row
    return None


def _simple_item(name, unit, frame, column):
    row = _latest_row(frame)
    if row is None:
        return MacroItem(name, None, unit, None, SOURCE)
    value = _num(row[column]) if column in frame.columns else None
    return MacroItem(name, value, unit, str(row["月份"]), SOURCE)


def _pmi_item(name, unit, frame, _column=None):
    row = _latest_row(frame)
    if row is None:
        return MacroItem(name, None, unit, None, SOURCE)
    value = _num(row["制造业-指数"]) if "制造业-指数" in frame.columns else None
    non_manufacturing = (
        _num(row["非制造业-指数"]) if "非制造业-指数" in frame.columns else None
    )
    note = f"非制造业指数 {non_manufacturing}" if non_manufacturing is not None else None
    return MacroItem(name, value, unit, str(row["月份"]), SOURCE, note)


def _fixed_asset_item(name, unit, frame, _column=None):
    row = _latest_row(frame)
    if row is None:
        return MacroItem(name, None, unit, None, SOURCE)
    note = "自年初累计同比（按累计值计算）"
    period = str(row["月份"])
    current = _num(row["自年初累计"]) if "自年初累计" in frame.columns else None
    key = _period_of(row)
    prior = None
    if key is not None:
        prior_row = _find_row(frame, key[0] - 1, key[1])
        if prior_row is not None and "自年初累计" in frame.columns:
            prior = _num(prior_row["自年初累计"])
    if current is None or prior is None or prior <= 0:
        return MacroItem(name, None, unit, period, SOURCE, note)
    return MacroItem(name, (current / prior - 1) * 100, unit, period, SOURCE, note)


def _trade_item(name, unit, frame, _column=None):
    row = _latest_row(frame)
    if row is None:
        return MacroItem(name, None, unit, None, SOURCE)
    export = _num(row["当月出口额-同比增长"]) if "当月出口额-同比增长" in frame.columns else None
    imports = _num(row["当月进口额-同比增长"]) if "当月进口额-同比增长" in frame.columns else None
    note = f"进口同比 {imports}%" if imports is not None else None
    return MacroItem(name, export, unit, str(row["月份"]), SOURCE, note)


def fetch_macro() -> MacroBlock:
    """Fetch the six macro series; a failed series becomes a ``None`` value."""
    import akshare as ak

    getters = (
        ("CPI", "%", lambda: _simple_item("CPI", "%", ak.macro_china_cpi(), "全国-同比增长")),
        ("PPI", "%", lambda: _simple_item("PPI", "%", ak.macro_china_ppi(), "当月同比增长")),
        ("PMI", "指数", lambda: _pmi_item("PMI", "指数", ak.macro_china_pmi())),
        (
            "社零",
            "%",
            lambda: _simple_item(
                "社零", "%", ak.macro_china_consumer_goods_retail(), "同比增长"
            ),
        ),
        (
            "固定资产投资",
            "%",
            lambda: _fixed_asset_item(
                "固定资产投资", "%", ak.macro_china_fixed_asset_investment()
            ),
        ),
        (
            "进出口",
            "%",
            lambda: _trade_item("进出口", "%", ak.macro_china_customs_trade()),
        ),
    )
    items = []
    for name, unit, get in getters:
        try:
            items.append(get())
        except Exception:
            logger.warning("宏观取数失败：%s", name, exc_info=True)
            items.append(MacroItem(name, None, unit, None, SOURCE))
    return MacroBlock(items=items)
