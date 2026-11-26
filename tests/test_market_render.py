import pandas as pd
import pytest

from market.fetch import (
    IndexQuote,
    Industries,
    MarketFacts,
    MarketNews,
    Sentiment,
    Turnover,
    _parse_industries,
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
            source="上交所/深交所",
        ),
        sentiment=Sentiment(
            limit_up=45,
            limit_down=3,
            broken=8,
            broken_rate=15.1,
            max_streak=5,
            as_of="2026-11-25",
            source="东财",
        ),
        industries=Industries(
            gainers=[("半导体", 3.2), ("电池", 2.1)],
            losers=[("银行", -1.5), ("保险", -0.9)],
            as_of="2026-11-25 15:00",
            note="仅当日，历史不可用",
            source="同花顺",
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
    assert report.startswith(
        "# A 股大盘复盘 2026-11-25\n"
        "行情截止：2026-11-25 15:00；行业/新闻为运行时刻快照"
    )


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
    assert "来源：不可用 | As of: 不可用" in report
    assert "## 数据缺口\n\n无" in report


def test_industries_parsed_from_frame_render_name_and_percentage():
    frame = pd.DataFrame({"板块": ["半导体", "银行"], "涨跌幅": [3.2, -1.5]})
    facts = MarketFacts(
        trade_date="2026-11-25",
        industries=_parse_industries(frame, "2026-11-25 15:00"),
    )

    report = render_market(facts, Summary(""))

    assert "涨幅前5：半导体 +3.2%" in report
    assert "跌幅前5：银行 -1.5%" in report
    assert "来源：同花顺 | As of: 2026-11-25 15:00" in report


def test_empty_indices_render_data_unavailable():
    report = render_market(MarketFacts(trade_date="2026-11-25"), Summary(""))

    assert "## 指数趋势\n\n数据不可用" in report


def test_gaps_render_as_bullets_and_northbound_is_absent():
    report = render_market(_full_facts(), Summary("指数放量上行。"))

    assert "## 数据缺口" in report
    assert "- news: 无可用条目" in report
    assert "北向资金" not in report


def _section(report: str, heading: str) -> str:
    after = report.split(f"## {heading}\n\n", 1)[1]
    return after.split("\n\n## ", 1)[0]


@pytest.mark.parametrize(
    ("trend", "expected"),
    [
        (Trend("上行", True, True, True), ("是", "是", "是")),
        (Trend("下行", False, False, False), ("否", "否", "否")),
        (Trend("震荡", True, True, False), ("是", "是", "否")),
    ],
)
def test_conclusion_lists_rule_conditions_before_model_text(trend, expected):
    facts = _full_facts()
    facts.trend = trend
    section = _section(render_market(facts, Summary("模型解释。")), "结论")

    assert section.splitlines()[:4] == [
        f"趋势：{trend.level}",
        f"收盘>MA20：{expected[0]}",
        f"MA20>MA60：{expected[1]}",
        f"20日涨跌>0：{expected[2]}",
    ]
    assert section.index(f"趋势：{trend.level}") < section.index("模型解释。")


def test_conclusion_keeps_rule_conditions_when_summary_failed():
    section = _section(
        render_market(_full_facts(), Summary("摘要生成失败")), "结论"
    )

    assert section.startswith(
        "趋势：上行\n收盘>MA20：是\nMA20>MA60：是\n20日涨跌>0：是"
    )
    assert "摘要生成失败" in section


def test_conclusion_without_trend_renders_three_unavailable():
    section = _section(
        render_market(MarketFacts(trade_date="2026-11-26"), Summary("")), "结论"
    )

    assert section.splitlines()[:4] == [
        "趋势：无法判定",
        "收盘>MA20：不可用",
        "MA20>MA60：不可用",
        "20日涨跌>0：不可用",
    ]


def test_index_table_footnote_names_volume_caliber():
    section = _section(render_market(_full_facts(), Summary("")), "指数趋势")

    assert "20日量能倍数按指数成交量计算（指数成交量口径）" in section
    assert section.index("| 上证 |") < section.index("20日量能倍数按指数成交量计算")


def test_dropped_note_lands_after_flag_bullets_in_conclusion():
    report = render_market(_full_facts(), Summary("指数放量上行。", dropped=1))
    section = _section(report, "结论")
    flag = "- 放量：沪深300 20 日量能倍数 1.30"
    note = "（已丢弃 1 句模型输出，含未提供数字）"

    assert section.splitlines()[-1] == note
    assert section.index(flag) < section.index(note)
    assert report.count(note) == 1


def test_none_index_fields_render_unavailable_without_stray_units():
    facts = MarketFacts(
        trade_date="2026-11-26",
        indices=[IndexQuote(name="上证", code="sh000001")],
    )

    report = render_market(facts, Summary(""))

    assert (
        "| 上证 | 不可用 | 不可用 | 不可用 | 不可用 | 不可用 "
        "| 不可用 | 不可用 | 不可用 |"
    ) in report
    assert _section(report, "指数趋势").endswith("来源：不可用 | As of: 不可用")
    assert "不可用%" not in report
    assert "不可用 亿元" not in report


def test_missing_turnover_renders_three_unavailable_and_source_line():
    report = render_market(MarketFacts(trade_date="2026-11-26"), Summary(""))

    section = _section(report, "两市成交额")
    assert "| 沪市 | 不可用 |" in section
    assert "| 深市 | 不可用 |" in section
    assert "| 合计 | 不可用 |" in section
    assert section.endswith("来源：不可用 | As of: 不可用")
    assert "不可用 亿元" not in section


def test_missing_sentiment_renders_five_unavailable_and_source_line():
    report = render_market(MarketFacts(trade_date="2026-11-26"), Summary(""))

    section = _section(report, "市场情绪")
    assert (
        "涨停 不可用 / 跌停 不可用 / 炸板 不可用；"
        "炸板率 不可用；最高连板 不可用"
    ) in section
    assert section.endswith("来源：不可用 | As of: 不可用")
    assert "不可用%" not in section


def test_missing_industries_renders_data_unavailable_and_source_line():
    report = render_market(MarketFacts(trade_date="2026-11-26"), Summary(""))

    section = _section(report, "行业强弱")
    assert "涨幅前5：数据不可用" in section
    assert "跌幅前5：数据不可用" in section
    assert section.endswith("来源：不可用 | As of: 不可用")


def test_empty_news_renders_data_unavailable_with_source_line():
    report = render_market(MarketFacts(trade_date="2026-11-26"), Summary(""))

    assert (
        "## 新闻与政策\n\n数据不可用\n\n来源：东财快讯 | As of: 不可用" in report
    )


def test_empty_gaps_render_none_marker():
    report = render_market(MarketFacts(trade_date="2026-11-26"), Summary(""))

    assert "## 数据缺口\n\n无" in report


def test_empty_indices_render_data_unavailable_for_pinned_date():
    report = render_market(MarketFacts(trade_date="2026-11-26"), Summary(""))

    assert "## 指数趋势\n\n数据不可用" in report
    assert "不可用%" not in report
    assert "不可用 亿元" not in report
