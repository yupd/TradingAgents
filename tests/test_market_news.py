from market import fetch

FORMATTED = """# 市场快讯（近 7 天）

- [东财快讯] 2026-11-26 10:30 三大指数集体高开
  https://example.com/a

- [东财快讯] 2026-11-26 09:15 央行开展逆回购操作
  https://example.com/b

- [东财快讯] 2026-11-25 16:02 北向资金今日净流入
  https://example.com/c

Source: 东财快讯 | As of: 2026-11-26 10:30
"""


def test_parses_three_items_with_title_source_time_url_and_note():
    news = fetch._parse_global_news(FORMATTED)
    assert len(news) == 3
    assert [item.title for item in news] == [
        "三大指数集体高开",
        "央行开展逆回购操作",
        "北向资金今日净流入",
    ]
    assert [item.source for item in news] == ["东财快讯"] * 3
    assert [item.published_at for item in news] == [
        "2026-11-26 10:30",
        "2026-11-26 09:15",
        "2026-11-25 16:02",
    ]
    # 裸 URL 行按需求忽略，不并入条目。
    assert [item.url for item in news] == [None, None, None]
    assert all(item.note == "媒体口径，未核实" for item in news)


def test_sentinels_and_empty_text_yield_no_items():
    assert fetch._parse_global_news("DATA_UNAVAILABLE: global news could not be fetched") == []
    assert fetch._parse_global_news("NO_DATA_AVAILABLE: no market flashes") == []
    assert fetch._parse_global_news("") == []
    assert fetch._parse_global_news("  \n") == []


def test_malformed_lines_are_skipped_without_raising():
    text = "\n".join(
        [
            "# 市场快讯（近 7 天）",
            "- [东财快讯] 不是日期 标题",
            "- 没有来源和方括号 2026-11-26 10:30 标题",
            "  https://example.com/a",
            "Source: 东财快讯 | As of: 2026-11-26 10:30",
            "- [东财快讯] 2026-11-26 10:30 有效标题",
        ]
    )
    news = fetch._parse_global_news(text)
    assert len(news) == 1
    assert news[0].title == "有效标题"


def test_fetch_news_passes_arguments_and_returns_parsed_items(monkeypatch):
    calls = []

    def fake(curr_date, look_back_days=7, limit=10):
        calls.append((curr_date, look_back_days, limit))
        return FORMATTED

    monkeypatch.setattr(fetch, "get_global_news", fake)
    result = fetch.fetch_news("2026-11-26", look_back_days=3, limit=2)
    assert calls == [("2026-11-26", 3, 2)]
    assert result.gap is None
    assert [item.title for item in result.items] == [
        "三大指数集体高开",
        "央行开展逆回购操作",
        "北向资金今日净流入",
    ]


def test_fetch_news_records_gap_when_source_raises(monkeypatch):
    def fake(curr_date, look_back_days=7, limit=10):
        raise ConnectionError("boom")

    monkeypatch.setattr(fetch, "get_global_news", fake)
    result = fetch.fetch_news("2026-11-26")
    assert result.items == []
    assert result.gap.startswith("news:")
    assert "ConnectionError" in result.gap


def test_fetch_news_records_gap_for_sentinel(monkeypatch):
    monkeypatch.setattr(
        fetch, "get_global_news", lambda *a, **kw: "DATA_UNAVAILABLE: global news down"
    )
    result = fetch.fetch_news("2026-11-26")
    assert result.items == []
    assert result.gap.startswith("news:")
