"""A-share announcements, broker research and market flashes, bounded by publish time."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from . import akshare_patch  # noqa: F401  (installs the Eastmoney wrapper)
from . import http
from .symbols import parse_ashare
from .types import AStockSymbol, NewsItem


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _cutoff(end_date: str) -> str:
    """A historical run sees only what was published by the close; a live run sees now."""
    now = _now()
    if end_date >= now[:10]:
        return now
    return f"{end_date} 15:00"


def _clean_stamp(value) -> str:
    text = str(value or "").replace("T", " ").strip()
    return text[:16] if len(text) >= 16 else text[:10]


def _load_announcements(sym: AStockSymbol, start: str, end: str) -> list[dict]:
    response = http.em_get(
        "https://np-anotice-stock.eastmoney.com/api/security/ann",
        params={"sr": -1, "page_size": 100, "page_index": 1, "ann_type": "A",
                "client_source": "web", "stock_list": sym.code,
                "begin_time": start, "end_time": end},
    )
    items = ((response.json().get("data") or {}).get("list")) or []
    return [{"title": item.get("title") or "", "published_at": _clean_stamp(item.get("notice_date")),
             "source": "东财公告",
             "url": (f"https://data.eastmoney.com/notices/detail/{sym.code}/"
                     f"{item.get('art_code')}.html" if item.get("art_code") else None)}
            for item in items]


def _load_research(sym: AStockSymbol, start: str, end: str) -> list[dict]:
    response = http.em_get(
        "https://reportapi.eastmoney.com/report/list",
        params={"code": sym.code, "pageSize": 50, "beginTime": start, "endTime": end,
                "qType": 0, "pageNo": 1},
    )
    items = response.json().get("data") or []
    return [{"title": item.get("title") or "", "published_at": _clean_stamp(item.get("publishDate")),
             "source": item.get("orgSName") or "券商研报",
             "url": item.get("pdfUrl") or None}
            for item in items]


def _items(raw: list[dict], start: str, end: str) -> list[NewsItem]:
    cutoff = _cutoff(end)
    kept = [NewsItem(**row) for row in raw
            if row["published_at"] and start <= row["published_at"][:10] and row["published_at"] <= cutoff]
    return kept


def get_announcements(sym: AStockSymbol, start: str, end: str) -> list[NewsItem]:
    return _items(_load_announcements(sym, start, end), start, end)


def get_research_reports(sym: AStockSymbol, start: str, end: str) -> list[NewsItem]:
    return _items(_load_research(sym, start, end), start, end)


def _format(items: list[NewsItem], title: str, as_of: str, errors: list[str]) -> str:
    if not items:
        if errors:
            return f"DATA_UNAVAILABLE: {title} for the window ({'; '.join(errors)})"
        return f"NO_DATA_AVAILABLE: no {title} in the window"
    lines = [f"# {title}", ""]
    for item in items:
        lines.append(f"- [{item.source}] {item.published_at} {item.title}")
        if item.url:
            lines.append(f"  {item.url}")
    lines.append(f"\nSource: {', '.join(sorted({i.source for i in items}))} | As of: {as_of}")
    return "\n".join(lines)


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    sym = parse_ashare(ticker)
    items, errors = [], []
    for name, load in (("公告", lambda: get_announcements(sym, start_date, end_date)),
                       ("研报", lambda: get_research_reports(sym, start_date, end_date))):
        try:
            items.extend(load())
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    items.sort(key=lambda i: i.published_at, reverse=True)
    return _format(items, f"{sym.display} 个股资讯 {start_date} ~ {end_date}", _cutoff(end_date), errors)


def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str:
    """Market-wide flashes from Eastmoney's global feed, newest first."""
    try:
        import akshare as ak

        frame = ak.stock_news_global_em()
    except Exception as exc:
        return f"DATA_UNAVAILABLE: global news could not be fetched ({type(exc).__name__}: {exc})"
    frame = frame.copy()
    stamp_col = "发布时间" if "发布时间" in frame.columns else frame.columns[0]
    frame[stamp_col] = pd.to_datetime(frame[stamp_col], errors="coerce")
    frame = frame.dropna(subset=[stamp_col])
    start = pd.Timestamp(curr_date) - pd.Timedelta(days=look_back_days)
    cutoff = (pd.Timestamp(f"{curr_date} 15:00") if curr_date < _now()[:10]
              else pd.Timestamp(_now()))
    frame = frame[(frame[stamp_col] >= start) & (frame[stamp_col] <= cutoff)].head(limit)
    if frame.empty:
        return f"NO_DATA_AVAILABLE: no market flashes between {start:%Y-%m-%d} and {cutoff}"
    items = [NewsItem(title=str(row.get("标题", "")), published_at=row[stamp_col].strftime("%Y-%m-%d %H:%M"),
                      source="东财快讯", url=row.get("链接")) for _, row in frame.iterrows()]
    as_of = items[0].published_at
    return _format(items, f"市场快讯（近 {look_back_days} 天）", as_of, [])
