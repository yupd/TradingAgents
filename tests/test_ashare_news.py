import tradingagents.dataflows.vendors.a_share.news as n
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

ITEMS = [
    {"title": "盘中公告", "published_at": "2026-06-01 10:00", "source": "东财"},
    {"title": "盘后公告", "published_at": "2026-06-01 16:30", "source": "东财"},
]


def test_history_cuts_at_close(monkeypatch):
    monkeypatch.setattr(n, "_load_announcements", lambda *a: ITEMS)
    titles = [i.title for i in n.get_announcements(parse_ashare("600519"), "2026-06-01", "2026-06-01")]
    assert titles == ["盘中公告"]


def test_live_run_includes_after_close(monkeypatch):
    monkeypatch.setattr(n, "_now", lambda: "2026-06-01 20:00")
    monkeypatch.setattr(n, "_load_announcements", lambda *a: ITEMS)
    titles = [i.title for i in n.get_announcements(parse_ashare("600519"), "2026-06-01", "2026-06-01")]
    assert titles == ["盘中公告", "盘后公告"]


def test_news_failure_returns_sentinel(monkeypatch):
    monkeypatch.setattr(n, "_load_announcements", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(n, "_load_research", lambda *a: [])
    monkeypatch.setattr(n, "_now", lambda: "2026-06-01 20:00")
    text = n.get_news("600519", "2026-06-01", "2026-06-01")
    assert "DATA_UNAVAILABLE" in text or "NO_DATA_AVAILABLE" in text


def test_global_news_cuts_at_close_and_skips_nat(monkeypatch):
    import pandas as pd
    import akshare as ak

    frame = pd.DataFrame({
        "标题": ["盘中", "盘后", "坏时间"],
        "摘要": ["a", "b", "c"],
        "发布时间": ["2026-06-01 10:00:00", "2026-06-01 16:30:00", "not-a-date"],
    })
    monkeypatch.setattr(ak, "stock_news_global_em", lambda: frame)
    text = n.get_global_news("2026-06-01", look_back_days=7, limit=10)
    assert "盘中" in text and "盘后" not in text
    assert "As of: 2026-06-01 10:00" in text
