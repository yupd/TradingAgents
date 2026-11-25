"""A-share statements and fundamentals, filtered by the date each period was announced."""

from __future__ import annotations

import pandas as pd

from . import http
from .symbols import parse_ashare
from .types import AStockSymbol, StatementRow

_REPORTS = {
    "income": "RPT_DMSK_FN_INCOME",
    "balance": "RPT_DMSK_FN_BALANCE",
    "cashflow": "RPT_DMSK_FN_CASHFLOW",
}
_LABELS = {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}
_META = {"REPORT_DATE", "NOTICE_DATE", "SECURITY_CODE", "SECURITY_NAME_ABBR", "DATA_STATE"}
_META_SUFFIXES = ("_CODE", "_DATE", "_TYPE", "_ID")


def _date(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value)[:10]
    return text if text[:4].isdigit() else None


def _load_statement(sym: AStockSymbol, kind: str, freq: str) -> list[dict]:
    """Statement rows from Eastmoney's datacenter; Sina is the fallback."""
    response = http.em_get(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={"reportName": _REPORTS[kind], "columns": "ALL",
                "filter": f'(SECURITY_CODE="{sym.code}")', "pageSize": 50,
                "sortColumns": "REPORT_DATE", "sortTypes": "-1"},
    )
    data = (response.json().get("result") or {}).get("data") or []
    if not data:
        raise RuntimeError("Eastmoney returned no statement rows")
    rows = []
    for item in data:
        period = _date(item.get("REPORT_DATE"))
        if period is None:
            continue
        if freq == "annual" and not period.endswith("12-31"):
            continue
        values = {}
        for key, value in item.items():
            if key in _META or key.endswith(_META_SUFFIXES):
                continue
            try:
                values[key] = float(value)
            except (TypeError, ValueError):
                continue
        rows.append({"period": period, "publish_date": _date(item.get("NOTICE_DATE")),
                     "values": values, "source": "eastmoney"})
    return rows


def _to_rows(raw: list[dict]) -> list[StatementRow]:
    rows = []
    for r in raw:
        values = r.get("values")
        if values is None:
            values = {k: float(v) for k, v in r.items()
                      if k not in ("period", "publish_date", "source")
                      and not k.endswith(_META_SUFFIXES) and isinstance(v, (int, float))}
        rows.append(StatementRow(period=r["period"], publish_date=r.get("publish_date"),
                                 values=values, source=r.get("source", "unknown")))
    return rows


def _select(sym: AStockSymbol, kind: str, freq: str, as_of: str | None):
    rows = _to_rows(_load_statement(sym, kind, freq))
    withheld_no_date = withheld_after = 0
    if as_of:
        kept = []
        for row in rows:
            if row.publish_date is None:
                withheld_no_date += 1
            elif row.publish_date > as_of:
                withheld_after += 1
            else:
                kept.append(row)
        rows = kept
    # One row per period: keep the version announced latest on or before as_of.
    by_period: dict[str, StatementRow] = {}
    for row in rows:
        current = by_period.get(row.period)
        if current is None or (row.publish_date or "") > (current.publish_date or ""):
            by_period[row.period] = row
    rows = sorted(by_period.values(), key=lambda r: r.period, reverse=True)
    return rows, {"no_date": withheld_no_date, "after": withheld_after}


def get_statement(sym: AStockSymbol, kind: str, freq: str, as_of: str | None) -> list[StatementRow]:
    return _select(sym, kind, freq, as_of)[0]


def _format(sym: AStockSymbol, kind: str, freq: str, as_of: str | None) -> str:
    rows, withheld = _select(sym, kind, freq, as_of)
    if not rows:
        return (f"NO_DATA_AVAILABLE: no {_LABELS[kind]} for {sym.display} "
                f"that was published by {as_of or 'now'}")
    columns = []
    for row in rows:
        for key in row.values:
            if key not in columns:
                columns.append(key)
    columns = columns[:6]
    header = "| Period | Published | " + " | ".join(columns) + " |"
    lines = [header, "|" + "---|" * (len(columns) + 2)]
    for row in rows:
        cells = [row.period, row.publish_date or "—"]
        cells += ["—" if key not in row.values else f"{row.values[key]:,.0f}" for key in columns]
        lines.append("| " + " | ".join(cells) + " |")
    footer = [f"Source: {rows[0].source} | As of: {as_of or 'latest'} | Freq: {freq} | 单位：元"]
    if withheld["no_date"]:
        footer.append(f"{withheld['no_date']} periods withheld: no publish date")
    if withheld["after"]:
        footer.append(f"{withheld['after']} periods withheld: published after {as_of}")
    return f"# {sym.display} {_LABELS[kind]}\n\n" + "\n".join(lines) + "\n\n" + "\n".join(footer)


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    try:
        return _format(parse_ashare(ticker), "income", freq, curr_date)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: statements for {ticker} ({type(exc).__name__}: {exc})"


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    try:
        return _format(parse_ashare(ticker), "balance", freq, curr_date)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: statements for {ticker} ({type(exc).__name__}: {exc})"


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str | None = None) -> str:
    try:
        return _format(parse_ashare(ticker), "cashflow", freq, curr_date)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: statements for {ticker} ({type(exc).__name__}: {exc})"


def get_fundamentals(ticker: str, curr_date: str | None = None) -> str:
    sym = parse_ashare(ticker)
    lines = [f"# {sym.display} 基本面"]
    try:
        from .quotes import get_snapshot
        snap = get_snapshot(sym)
        label = "current snapshot, not historical" if curr_date else "current"
        lines += [f"- 名称：{snap.name}（{label}）", f"- 最新价：{snap.price:.2f}",
                  f"- PE(TTM)：{'—' if snap.pe_ttm is None else f'{snap.pe_ttm:.2f}'}",
                  f"- PB：{'—' if snap.pb is None else f'{snap.pb:.2f}'}"]
    except Exception as exc:
        lines.append(f"- 估值不可用：{exc}")
    try:
        latest = get_statement(sym, "income", "quarterly", curr_date)[:1]
        for row in latest:
            lines.append(f"- 最近报告期：{row.period}（公告 {row.publish_date or '—'}）")
    except Exception as exc:
        lines.append(f"- 财务摘要不可用：{exc}")
    lines.append(f"\nSource: tencent/eastmoney | As of: {curr_date or 'now'}")
    return "\n".join(lines)
