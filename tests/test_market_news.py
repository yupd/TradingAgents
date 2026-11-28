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


def test_parses_items_and_drops_northbound_ones():
    news = fetch._parse_global_news(FORMATTED)
    assert len(news) == 2
    assert [item.title for item in news] == [
        "三大指数集体高开",
        "央行开展逆回购操作",
    ]
    assert [item.source for item in news] == ["东财快讯"] * 2
    assert [item.published_at for item in news] == [
        "2026-11-26 10:30",
        "2026-11-26 09:15",
    ]
    # 裸 URL 行按需求忽略，不并入条目。
    assert [item.url for item in news] == [None, None]
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


def _news(title):
    return fetch.MarketNews(
        title=title,
        published_at="2026-11-27 17:00",
        source="东财快讯",
    )


def test_filter_market_news_keeps_market_titles_and_drops_foreign_local_noise():
    items = [
        _news("三大指数集体高开"),
        _news("央行开展逆回购操作"),
        _news("国常会部署加力稳市"),
        _news("英伟达停止向中国输出H200芯片"),
        _news("花旗：中国ETF单周净流入283亿美元"),
        _news("贵州茅台：中期利润分配拟每股派现25.6元"),
        _news("俄罗斯考虑对来自不友好国家的海产品进口征收关税"),
        _news("波兰延长全国警戒级别至明年2月底"),
        _news("德国新劳资协议允许企业协商延长工时或削减福利"),
    ]

    kept = fetch.filter_market_news(items)

    assert [item.title for item in kept] == [
        "三大指数集体高开",
        "央行开展逆回购操作",
        "国常会部署加力稳市",
        "英伟达停止向中国输出H200芯片",
        "花旗：中国ETF单周净流入283亿美元",
        "贵州茅台：中期利润分配拟每股派现25.6元",
    ]


def test_filter_market_news_is_case_insensitive_for_ascii_keywords():
    items = [
        _news("ai算力需求爆发"),
        _news("etf资金持续流入"),
        _news("IPO节奏放缓"),
        _news("普通公司新闻"),
    ]

    kept = fetch.filter_market_news(items)

    assert [item.title for item in kept] == [
        "ai算力需求爆发",
        "etf资金持续流入",
        "IPO节奏放缓",
    ]


def test_fetch_news_records_gap_when_all_items_are_noise(monkeypatch):
    text = "\n".join(
        [
            "# 市场快讯（近 7 天）",
            "- [东财快讯] 2026-11-27 17:00 俄罗斯考虑对海产品进口征收关税",
            "- [东财快讯] 2026-11-27 16:00 波兰延长全国警戒级别",
        ]
    )
    monkeypatch.setattr(fetch, "get_global_news", lambda *a, **kw: text)

    result = fetch.fetch_news("2026-11-27")

    assert result.items == []
    assert result.gap == "news: 无市场相关条目"


def _flash_lines(count: int, market_at: int | None = None) -> list[str]:
    """Vendor markdown with ``count`` noise flashes; ``market_at`` (1-based) is the market one."""
    lines = [f"- [东财快讯] 2026-11-26 10:00 普通公司新闻 {n}" for n in range(1, count + 1)]
    if market_at is not None:
        lines[market_at - 1] = "- [东财快讯] 2026-11-26 10:00 央行开展逆回购操作"
    return lines


def test_fetch_news_filters_before_truncating(monkeypatch):
    def fake(curr_date, look_back_days=7, limit=10):
        # 模拟 vendor 的 head(limit)：只在源端先截断，关键词过滤在 fetch_news 之后。
        return "\n".join(_flash_lines(200, market_at=15)[:limit])

    monkeypatch.setattr(fetch, "get_global_news", fake)
    result = fetch.fetch_news("2026-11-26", limit=10)

    assert [item.title for item in result.items] == ["央行开展逆回购操作"]
    assert len(result.items) <= 10


def test_fetch_news_gap_when_no_keyword_matches(monkeypatch):
    def fake(curr_date, look_back_days=7, limit=10):
        return "\n".join(_flash_lines(200)[:limit])

    monkeypatch.setattr(fetch, "get_global_news", fake)
    result = fetch.fetch_news("2026-11-26", limit=10)

    assert result.items == []
    assert result.gap == "news: 无市场相关条目"
