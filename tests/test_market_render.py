from market.fetch import (
    IndexQuote,
    Industries,
    MarketFacts,
    MarketNews,
    Sentiment,
    Turnover,
)
from market.render import render_market
from market.rules import Flag, Trend
from market.summarize import Summary


def _full_facts() -> MarketFacts:
    return MarketFacts(
        trade_date="2026-11-25",
        indices=[
            IndexQuote(
                name="上证",
                code="sh000001",
                close=3456.78,
                change_pct=1.23,
                return_5d=2.10,
                return_20d=3.40,
                return_60d=-1.20,
                ma20=3400.00,
                ma60=3350.00,
                volume_ratio=1.15,
                source="tencent",
                as_of="2026-11-25",
            )
        ],
        turnover=Turnover(
            sh=5000.12,
            sz=6500.34,
            total=11500.46,
            note="沪深股票成交额",
            as_of="2026-11-25",
        ),
        sentiment=Sentiment(
            limit_up=45,
            limit_down=3,
            broken=8,
            broken_rate=15.1,
            max_streak=5,
            as_of="2026-11-25",
        ),
        industries=Industries(
            gainers=[("半导体", 3.2), ("电池", 2.1)],
            losers=[("银行", -1.5), ("保险", -0.9)],
            as_of="2026-11-25 15:00",
            note="仅当日，历史不可用",
        ),
        news=[
            MarketNews(title="央行降准", published_at="2026-11-25 09:00", source="东财")
        ],
        trend=Trend("上行", True, True, True),
        flags=[Flag("volume_up", "放量", "沪深300 20 日量能倍数 1.30")],
        gaps=["news: 无可用条目"],
    )


def test_seven_sections_appear_in_fixed_order():
    report = render_market(_full_facts(), Summary("指数放量上行。"))
    headings = [line for line in report.splitlines() if line.startswith("## ")]
    assert headings == [
        "## 结论",
        "## 指数趋势",
        "## 两市成交额",
        "## 市场情绪",
        "## 行业强弱",
        "## 新闻与政策",
        "## 数据缺口",
    ]
    assert report.startswith("# A 股大盘复盘 2026-11-25\n数据截止：2026-11-25 15:00")


def test_full_facts_render_values_flags_sources_and_news_label():
    report = render_market(_full_facts(), Summary("指数放量上行。"))

    assert "趋势：上行" in report
    assert "指数放量上行。" in report
    assert "- 放量：沪深300 20 日量能倍数 1.30" in report

    assert (
        "| 上证 | 3456.78 | +1.23% | +2.10% | +3.40% | -1.20% "
        "| 3400.00 | 3350.00 | 1.15 |"
    ) in report
    assert "来源：tencent | As of: 2026-11-25" in report

    assert "| 沪市 | 5000.12 亿元 |" in report
    assert "| 合计 | 11500.46 亿元 |" in report
    assert "说明：沪深股票成交额" in report
    assert "来源：上交所/深交所 | As of: 2026-11-25" in report

    assert "涨停 45 / 跌停 3 / 炸板 8；炸板率 15.1%；最高连板 5" in report
    assert "来源：东财 | As of: 2026-11-25" in report

    assert "涨幅前5：半导体 +3.2% 电池 +2.1%" in report
    assert "跌幅前5：银行 -1.5% 保险 -0.9%" in report
    assert "说明：仅当日，历史不可用" in report
    assert "来源：同花顺 | As of: 2026-11-25 15:00" in report

    assert "- [东财 2026-11-25 09:00] 央行降准（媒体口径，未核实）" in report


def test_partial_facts_mark_unavailable_without_units_or_errors():
    facts = MarketFacts(
        trade_date="2026-11-25",
        indices=[IndexQuote(name="上证", code="sh000001")],
    )

    report = render_market(facts, Summary(""))

    assert "不可用%" not in report
    assert "不可用 亿元" not in report
    assert "趋势：无法判定" in report
    assert "数据不可用" in report
    assert "来源：东财 | As of: 不可用" in report
    assert "## 数据缺口\n\n无" in report


def test_gaps_render_as_bullets_and_northbound_is_absent():
    report = render_market(_full_facts(), Summary("指数放量上行。"))

    assert "## 数据缺口" in report
    assert "- news: 无可用条目" in report
    assert "北向资金" not in report
