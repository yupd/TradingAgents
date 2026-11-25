"""A-share fund-flow, hot-money and event signals."""

from __future__ import annotations

from datetime import datetime

from . import http
from .symbols import parse_ashare
from .types import AStockSymbol


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _within(date: str, curr_date: str) -> bool:
    """A historical run excludes the same day's after-close disclosures."""
    return date < curr_date if curr_date < _today() else date <= curr_date


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
    parsed = [row for row in parsed if _within(row["date"], curr_date)]
    return parsed[-20:] if include_history else parsed[-1:]


def get_fund_flow(ticker: str, curr_date: str, include_history: bool = True) -> str:
    sym = parse_ashare(ticker)
    try:
        rows = [row for row in _fetch_fund_flow(sym, curr_date, include_history)
                if _within(row["date"], curr_date)]
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
        if date and _within(date, trade_date):
            if item.get("NET_BUY_AMT") is None:
                raise RuntimeError("dragon-tiger board row has no NET_BUY_AMT")
            rows.append({"date": date, "seat": item.get("OPERATEDEPT_NAME") or "—",
                         "net": float(item["NET_BUY_AMT"])})
    return rows[: max(1, look_back_days)]


def get_dragon_tiger_board(ticker: str, curr_date: str, look_back_days: int = 30) -> str:
    sym = parse_ashare(ticker)
    try:
        rows = [row for row in _fetch_lhb(sym, curr_date, look_back_days)
                if _within(row["date"], curr_date)]
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
    frame = frame[[_within(value, curr_date) for value in frame[date_col]]].tail(20 if include_history else 1)
    if frame.empty:
        return f"NO_DATA_AVAILABLE: no northbound flow up to {curr_date}"
    value_col = "当日成交净买额" if "当日成交净买额" in frame.columns else frame.columns[1]
    lines = [f"# 北向资金（截至 {curr_date}）", "", "| 日期 | 净买额 |", "|---|---|"]
    lines += [f"| {row[date_col]} | {row[value_col]} |" for _, row in frame.iterrows()]
    lines.append(f"\nSource: eastmoney | As of: {frame.iloc[-1][date_col]}")
    return "\n".join(lines)


def _fetch_lockups(sym: AStockSymbol) -> list[dict]:
    response = http.em_get(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={"reportName": "RPT_LIFT_STAGE", "columns": "ALL",
                "filter": f'(SECURITY_CODE="{sym.code}")', "pageSize": 50,
                "sortColumns": "FREE_DATE", "sortTypes": "1"},
    )
    items = (response.json().get("result") or {}).get("data") or []
    return [{"announced": str(item.get("NOTICE_DATE") or "")[:10],
             "expiry": str(item.get("FREE_DATE") or "")[:10],
             "ratio": float(item.get("LIFT_MARKET_CAP_RATIO") or 0)} for item in items]


def get_lockup_expiry(ticker: str, curr_date: str, forward_days: int = 90) -> str:
    from datetime import timedelta

    sym = parse_ashare(ticker)
    try:
        rows = _fetch_lockups(sym)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: lockup expiry for {sym.display} ({exc})"
    horizon = (datetime.strptime(curr_date, "%Y-%m-%d") + timedelta(days=forward_days)).strftime("%Y-%m-%d")
    kept = [row for row in rows
            if row["announced"] and row["announced"] <= curr_date
            and curr_date <= row["expiry"] <= horizon]
    if not kept:
        return f"NO_DATA_AVAILABLE: no lockup expiry for {sym.display} in the next {forward_days} days"
    lines = [f"# {sym.display} 解禁日历（未来 {forward_days} 天）", "",
             "| 解禁日 | 占总市值 |", "|---|---|"]
    lines += [f"| {row['expiry']} | {row['ratio']:.2f}% |" for row in kept]
    lines.append(f"\nSource: eastmoney | As of: {curr_date}")
    return "\n".join(lines)


def _fetch_forecast(sym: AStockSymbol) -> dict:
    # shortcut: AkShare 的预期接口列名随版本漂移，取不到就降级为不可用；后续可换东财直连。
    import akshare as ak

    frame = ak.stock_profit_forecast_em(symbol=sym.code)
    if frame is None or frame.empty:
        raise RuntimeError("no forecast rows")
    row = frame.iloc[0]
    eps_col = next((column for column in frame.columns if "每股收益" in str(column)), None)
    coverage_col = next((column for column in frame.columns if "机构" in str(column)), None)
    if eps_col is None or coverage_col is None:
        raise RuntimeError("consensus forecast columns are missing")
    return {"eps": float(row[eps_col]), "coverage": int(row[coverage_col])}


def get_profit_forecast(ticker: str, curr_date: str) -> str:
    sym = parse_ashare(ticker)
    try:
        data = _fetch_forecast(sym)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: consensus forecast for {sym.display} ({exc})"
    note = ("\n\ncurrent snapshot, not historical：一致预期没有历史时点值，"
            f"这里展示的是当前版本，不是 {curr_date} 当天的预期。"
            if curr_date < _today() else "")
    return (f"# {sym.display} 一致预期\n\n- EPS：{data['eps']:.2f}\n"
            f"- 覆盖机构：{data['coverage']}\n\nSource: eastmoney | As of: {_today()}{note}")


def _fetch_industry(sym: AStockSymbol, top_n: int) -> list[dict]:
    # shortcut: 行业对比用全市场行业榜代替个股所属行业，够用但不够精确。
    import akshare as ak

    frame = ak.stock_board_industry_name_em().sort_values("涨跌幅", ascending=False).head(top_n)
    return [{"name": row.get("板块名称", ""), "change": float(row.get("涨跌幅", 0) or 0)}
            for _, row in frame.iterrows()]


def get_industry_comparison(ticker: str, curr_date: str, top_n: int = 20) -> str:
    sym = parse_ashare(ticker)
    try:
        rows = _fetch_industry(sym, top_n)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: industry comparison for {sym.display} ({exc})"
    if not rows:
        return f"NO_DATA_AVAILABLE: no industry comparison for {sym.display}"
    lines = [f"# {sym.display} 行业对比（涨幅前 {top_n}）", "", "| 行业 | 涨跌幅 |", "|---|---|"]
    lines += [f"| {row['name']} | {row['change']:.2f}% |" for row in rows]
    note = (f"\n\ncurrent snapshot, not historical：请求日为 {curr_date}。"
            if curr_date < _today() else "")
    lines.append(f"\nSource: eastmoney | As of: {_today()}{note}")
    return "\n".join(lines)


def _fetch_holders(sym: AStockSymbol) -> list[dict]:
    response = http.em_get(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={"reportName": "RPT_SHARE_HOLDER_INCREASE", "columns": "ALL",
                "filter": f'(SECURITY_CODE="{sym.code}")', "pageSize": 50,
                "sortColumns": "NOTICE_DATE", "sortTypes": "-1"},
    )
    items = (response.json().get("result") or {}).get("data") or []
    rows = []
    for item in items:
        shares = item.get("CHANGE_SHARES") if item.get("CHANGE_SHARES") is not None else item.get("CHANGE_NUM")
        date = str(item.get("NOTICE_DATE") or "")[:10]
        if shares is None or not date:
            raise RuntimeError("shareholder-change row is missing shares or NOTICE_DATE")
        rows.append({"date": date, "name": item.get("HOLDER_NAME") or "—",
                     "change": float(shares) / 1e4})
    return rows


def get_insider_transactions(ticker: str, curr_date: str | None = None) -> str:
    """A-share shareholder/executive changes: 增持 or 减持, in 万股."""
    sym = parse_ashare(ticker)
    try:
        rows = _fetch_holders(sym)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: shareholder changes for {sym.display} ({exc})"
    cutoff = curr_date or _today()
    rows = [row for row in rows if _within(row["date"], cutoff)]
    if not rows:
        return f"NO_DATA_AVAILABLE: no shareholder changes for {sym.display} up to {cutoff}"
    lines = [f"# {sym.display} 股东/高管增减持", ""]
    for row in rows[:20]:
        action = "增持" if row["change"] >= 0 else "减持"
        lines.append(f"- {row['date']} {row['name']} {action} {abs(row['change']):,.2f} 万股")
    lines.append(f"\nSource: eastmoney | As of: {rows[0]['date']}")
    return "\n".join(lines)
