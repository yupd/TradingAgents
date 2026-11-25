"""A-share fund-flow, hot-money and event signals."""

from __future__ import annotations

from datetime import datetime

from . import http
from .symbols import parse_ashare
from .types import AStockSymbol


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _market_id(sym: AStockSymbol) -> str:
    return "1" if sym.exchange == "SH" else "0"


def _fetch_fund_flow(sym: AStockSymbol, curr_date: str, include_history: bool) -> list[dict]:
    response = http.em_get(
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
        params={"secid": f"{_market_id(sym)}.{sym.code}",
                "fields1": "f1,f2,f3,f7", "fields2": "f51,f52,f53,f54,f55,f56",
                "klt": 101, "lmt": 0},
    )
    rows = ((response.json().get("data") or {}).get("klines")) or []
    parsed = []
    for line in rows:
        parts = line.split(",")
        parsed.append({"date": parts[0], "main_net": float(parts[1])})
    parsed = [row for row in parsed if row["date"] <= curr_date]
    return parsed[-20:] if include_history else parsed[-1:]


def get_fund_flow(ticker: str, curr_date: str, include_history: bool = True) -> str:
    sym = parse_ashare(ticker)
    try:
        rows = _fetch_fund_flow(sym, curr_date, include_history)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: fund flow for {sym.display} ({exc})"
    if not rows:
        return f"NO_DATA_AVAILABLE: no fund flow for {sym.display} up to {curr_date}"
    lines = [f"# {sym.display} 资金流", "", "| 日期 | 主力净流入(万元) |", "|---|---|"]
    lines += [f"| {row['date']} | {row['main_net'] / 1e4:,.0f} |" for row in rows]
    lines.append(f"\nSource: eastmoney | As of: {rows[-1]['date']}")
    return "\n".join(lines)


def _fetch_lhb(sym: AStockSymbol, trade_date: str, look_back_days: int) -> list[dict]:
    response = http.em_get(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={"reportName": "RPT_DAILYBILLBOARD_DETAILSNEW", "columns": "ALL",
                "filter": f'(SECURITY_CODE="{sym.code}")', "pageSize": 100,
                "sortColumns": "TRADE_DATE", "sortTypes": "-1"},
    )
    items = (response.json().get("result") or {}).get("data") or []
    rows = []
    for item in items:
        date = str(item.get("TRADE_DATE") or "")[:10]
        if date and date <= trade_date:
            rows.append({"date": date, "seat": item.get("OPERATEDEPT_NAME") or "—",
                         "net": float(item.get("NET_BUY_AMT") or 0)})
    return rows[: max(1, look_back_days)]


def get_dragon_tiger_board(ticker: str, curr_date: str, look_back_days: int = 30) -> str:
    sym = parse_ashare(ticker)
    try:
        rows = _fetch_lhb(sym, curr_date, look_back_days)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: dragon-tiger board for {sym.display} ({exc})"
    if not rows:
        return f"NO_DATA_AVAILABLE: {sym.display} was not on the dragon-tiger board in the window"
    lines = [f"# {sym.display} 龙虎榜", "", "| 日期 | 营业部 | 净买入(万元) |", "|---|---|---|"]
    lines += [f"| {row['date']} | {row['seat']} | {row['net'] / 1e4:,.0f} |" for row in rows]
    lines.append(f"\nSource: eastmoney | As of: {rows[0]['date']}")
    return "\n".join(lines)


def get_hot_stocks(curr_date: str = "") -> str:
    if curr_date and curr_date < _today():
        return f"历史日期不提供实时快照：热门榜只有当前版本（请求日 {curr_date}）"
    try:
        import akshare as ak

        frame = ak.stock_hot_rank_em().head(20)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: hot stocks ({exc})"
    lines = [f"# 热门股榜（{_today()}）", "", "| 代码 | 名称 | 排名 |", "|---|---|---|"]
    for _, row in frame.iterrows():
        lines.append(f"| {row.get('代码', '—')} | {row.get('股票名称', '—')} | {row.get('当前排名', '—')} |")
    lines.append(f"\nSource: eastmoney | As of: {_today()}")
    return "\n".join(lines)


def get_concept_blocks(ticker: str) -> str:
    sym = parse_ashare(ticker)
    code = f"{sym.exchange}{sym.code}"
    try:
        response = http.em_get("https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax",
                               params={"code": code})
        blocks = ((response.json().get("ssbk")) or [])
    except Exception as exc:
        return f"DATA_UNAVAILABLE: concept blocks for {sym.display} ({exc})"
    if not blocks:
        return f"NO_DATA_AVAILABLE: no concept blocks for {sym.display}"
    lines = [f"# {sym.display} 板块归属", ""]
    lines += [f"- {item.get('BOARD_NAME') or item.get('板块名称') or '—'}" for item in blocks]
    lines.append(f"\nSource: eastmoney | As of: {_today()}")
    return "\n".join(lines)


def get_northbound_flow(curr_date: str, include_history: bool = False) -> str:
    try:
        import akshare as ak

        frame = ak.stock_hsgt_hist_em(symbol="北向资金")
    except Exception as exc:
        return f"DATA_UNAVAILABLE: northbound flow ({exc})"
    frame = frame.copy()
    date_col = "日期" if "日期" in frame.columns else frame.columns[0]
    frame[date_col] = frame[date_col].astype(str).str[:10]
    frame = frame[frame[date_col] <= curr_date].tail(20 if include_history else 1)
    if frame.empty:
        return f"NO_DATA_AVAILABLE: no northbound flow up to {curr_date}"
    value_col = "当日成交净买额" if "当日成交净买额" in frame.columns else frame.columns[1]
    lines = [f"# 北向资金（截至 {curr_date}）", "", "| 日期 | 净买额 |", "|---|---|"]
    lines += [f"| {row[date_col]} | {row[value_col]} |" for _, row in frame.iterrows()]
    lines.append(f"\nSource: eastmoney | As of: {frame.iloc[-1][date_col]}")
    return "\n".join(lines)
