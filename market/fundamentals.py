"""Market-wide fundamentals; each source degrades to ``None`` instead of failing."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SOURCE = "akshare 宏观接口（东方财富/国家统计局口径）"
PE_SOURCE = "乐咕乐股（akshare）"
OFFICIAL_SOURCE = "中证指数（akshare）"
MARGIN_SOURCE = "上交所/深交所（akshare）"
EARNINGS_SOURCE = "东财业绩报表（akshare）"
EARNINGS_NOTE = "按个股财报加权聚合，非官方指数口径"
PERCENTILE_MONTHS = 120
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
    announcement_cutoff: str | None = None
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


def _pmi_item(name, unit, frame):
    row = _latest_row(frame)
    if row is None:
        return MacroItem(name, None, unit, None, SOURCE)
    value = _num(row["制造业-指数"]) if "制造业-指数" in frame.columns else None
    non_manufacturing = (
        _num(row["非制造业-指数"]) if "非制造业-指数" in frame.columns else None
    )
    note = f"非制造业指数 {non_manufacturing}" if non_manufacturing is not None else None
    return MacroItem(name, value, unit, str(row["月份"]), SOURCE, note)


def _fixed_asset_item(name, unit, frame):
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


def _trade_item(name, unit, frame):
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


def _iso_date(value) -> str | None:
    """Normalize akshare date cells (date, Timestamp, str, NaT) to ``YYYY-MM-DD``."""
    text = str(value)[:10] if value is not None else ""
    return text if len(text) == 10 else None


def _valuation_history(trade_date: str):
    """Latest TTM PE, its monthly percentile and window from the 沪深300 series."""
    import akshare as ak

    frame = ak.stock_index_pe_lg(symbol="沪深300")
    if (
        frame is None
        or frame.empty
        or "日期" not in frame.columns
        or "滚动市盈率" not in frame.columns
    ):
        return None
    rows = []
    for _, row in frame.iterrows():
        day = _iso_date(row.get("日期"))
        value = _num(row.get("滚动市盈率"))
        if day is not None and day <= trade_date and value is not None:
            rows.append((day, value))
    if not rows:
        return None
    rows.sort()
    window = rows[-PERCENTILE_MONTHS:]
    latest_date, latest = window[-1]
    percentile = round(sum(1 for _, value in window if value <= latest) / len(window) * 100, 1)
    return latest, percentile, len(window), latest_date


def _official_valuation(trade_date: str):
    """Latest official CSI 300 PE/dividend rows at or before ``trade_date``."""
    import akshare as ak

    frame = ak.index_value_csindex(symbol="000300")
    if frame is None or frame.empty or "日期" not in frame.columns:
        return None
    best = None
    for _, row in frame.iterrows():
        day = _iso_date(row.get("日期"))
        if day is not None and day <= trade_date and (best is None or day > best[0]):
            best = (day, row)
    if best is None:
        return None
    row = best[1]

    def column(name):
        return _num(row.get(name)) if name in frame.columns else None

    return (
        column("市盈率1"),
        column("市盈率2"),
        column("股息率1"),
        column("股息率2"),
        best[0],
    )


def fetch_valuation(trade_date: str) -> Valuation:
    """Third-party percentile and official CSI 300 values; each source degrades alone."""
    valuation = Valuation()
    sources = []
    try:
        history = _valuation_history(trade_date)
    except Exception:
        logger.warning("估值历史取数失败", exc_info=True)
        history = None
    if history is not None:
        (
            valuation.pe_ttm,
            valuation.pe_percentile,
            valuation.percentile_window,
            valuation.pe_date,
        ) = history
        sources.append(PE_SOURCE)
    try:
        official = _official_valuation(trade_date)
    except Exception:
        logger.warning("中证估值取数失败", exc_info=True)
        official = None
    # A frame with none of the four value columns is not a usable official source.
    if official is not None and any(value is not None for value in official[:4]):
        (
            valuation.official_pe1,
            valuation.official_pe2,
            valuation.official_div1,
            valuation.official_div2,
            valuation.official_date,
        ) = official
        sources.append(OFFICIAL_SOURCE)
    valuation.source = " / ".join(sources) if sources else None
    return valuation


def _margin_series(fetch, trade_date: str) -> dict[str, float]:
    """``date -> 融资融券余额（亿元）`` for rows at or before ``trade_date``."""
    frame = fetch()
    if (
        frame is None
        or frame.empty
        or "日期" not in frame.columns
        or "融资融券余额" not in frame.columns
    ):
        return {}
    series = {}
    for _, row in frame.iterrows():
        day = _iso_date(row.get("日期"))
        value = _num(row.get("融资融券余额"))
        if day is not None and day <= trade_date and value is not None:
            series[day] = value / 1e8  # akshare reports 元
    return series


def _combine_margin(sh: dict[str, float], sz: dict[str, float]) -> Margin:
    """Align both markets on common dates; totals need both sides."""
    common = sorted(set(sh) & set(sz))
    if common:
        latest = common[-1]
        total = sh[latest] + sz[latest]
        change = None
        if len(common) >= 6:
            prior = common[-6]
            change = round(total - (sh[prior] + sz[prior]), 2)
        return Margin(
            sh=round(sh[latest], 2),
            sz=round(sz[latest], 2),
            total=round(total, 2),
            change_5d=change,
            as_of=latest,
            source=MARGIN_SOURCE,
        )
    if not sh and not sz:
        return Margin()
    both_present = bool(sh) and bool(sz)
    if both_present:  # no shared date: report only the later side, never merge dates
        if max(sz) > max(sh):
            sh = {}
        else:
            sz = {}
    side = sh or sz
    latest = max(side)
    if both_present:
        note = "两市无共同日期，仅报可用单市"
    elif sh:
        note = "仅沪市数据可用，合计与 5 日变化不可用"
    else:
        note = "仅深市数据可用，合计与 5 日变化不可用"
    return Margin(
        sh=round(sh[latest], 2) if sh else None,
        sz=round(sz[latest], 2) if sz else None,
        as_of=latest,
        source="上交所（akshare）" if sh else "深交所（akshare）",
        note=note,
    )


def fetch_margin(trade_date: str) -> Margin:
    """SSE and SZSE margin balances; a failed side degrades, both failing stays empty."""
    import akshare as ak

    series = []
    for name, attribute in (
        ("沪市", "stock_margin_sse_js"),
        ("深市", "stock_margin_szse_js"),
    ):
        try:
            fetch = getattr(ak, attribute, None)
            if fetch is None:
                raise AttributeError(f"akshare 缺少 {attribute}")
            series.append(_margin_series(fetch, trade_date))
        except Exception:
            logger.warning("两融取数失败：%s", name, exc_info=True)
            series.append({})
    return _combine_margin(series[0], series[1])


def latest_report_period(trade_date: str) -> str:
    """Most recent quarter-end (03-31/06-30/09-30/12-31) at or before ``trade_date``."""
    year, month, day = (int(part) for part in trade_date[:10].split("-"))
    for end_month, end_day in ((12, 31), (9, 30), (6, 30), (3, 31)):
        if (month, day) >= (end_month, end_day):
            return f"{year:04d}-{end_month:02d}-{end_day:02d}"
    return f"{year - 1:04d}-12-31"


def _aggregate_yoy(rows, value_column, yoy_column):
    """Weighted YoY over rows where both the value and its YoY are usable."""
    current = prior = 0.0
    for row in rows:
        value = _num(row.get(value_column))
        yoy = _num(row.get(yoy_column))
        if value is None or yoy is None or yoy == -100:
            continue
        current += value
        prior += value / (1 + yoy / 100)
    if prior <= 0:
        return None
    return round((current / prior - 1) * 100, 2)


def _parse_earnings(frame, trade_date: str, period: str) -> Earnings | None:
    """Filter by announcement date and aggregate weighted YoY plus coverage."""
    if frame is None or getattr(frame, "empty", True):
        return None
    rows = []
    for _, row in frame.iterrows():
        day = _iso_date(row.get("最新公告日期"))
        if day is not None and day <= trade_date:
            rows.append(row)
    total = len(frame)
    coverage = len(rows) / total if total else None
    return Earnings(
        period=period,
        announcement_cutoff=trade_date,
        net_profit_yoy=_aggregate_yoy(rows, "净利润-净利润", "净利润-同比增长"),
        revenue_yoy=_aggregate_yoy(
            rows, "营业总收入-营业总收入", "营业总收入-同比增长"
        ),
        coverage=coverage,
        covered=len(rows),
        total=total,
        coverage_low=coverage is not None and coverage < 0.8,
        source=EARNINGS_SOURCE,
        note=EARNINGS_NOTE,
    )


def fetch_earnings(trade_date: str) -> Earnings | None:
    """Latest reported quarter aggregated across companies; failure or empty table is ``None``."""
    import akshare as ak

    period = latest_report_period(trade_date)
    try:
        frame = ak.stock_yjbb_em(date=period.replace("-", ""))
    except Exception:
        logger.warning("业绩报表取数失败", exc_info=True)
        return None
    return _parse_earnings(frame, trade_date, period)


def fetch_fundamentals(trade_date: str, is_latest: bool) -> Fundamentals:
    """The four fundamentals blocks; history gets no request and a fixed reason."""
    if not is_latest:
        return Fundamentals(unavailable="历史模式不可用")
    blocks = {}
    for name, fetch, args in (
        ("macro", fetch_macro, ()),
        ("valuation", fetch_valuation, (trade_date,)),
        ("margin", fetch_margin, (trade_date,)),
        ("earnings", fetch_earnings, (trade_date,)),
    ):
        try:
            blocks[name] = fetch(*args)
        except Exception:
            logger.warning("%s 取数失败", name, exc_info=True)
            blocks[name] = None
    return Fundamentals(**blocks)
