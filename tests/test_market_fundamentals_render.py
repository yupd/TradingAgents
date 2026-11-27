"""Rendering the four fundamentals sections, including history and degraded blocks."""

from market.fetch import MarketFacts
from market.fundamentals import (
    Earnings,
    Fundamentals,
    MacroBlock,
    MacroItem,
    Margin,
    Valuation,
)
from market.render import render_market
from market.rules import collect_gaps
from market.summarize import Summary

DAY = "2026-11-26"
MACRO_SOURCE = "akshare 宏观接口（国家统计局口径）"
PE_SOURCE = "乐咕乐股（akshare）"
OFFICIAL_SOURCE = "中证指数（akshare）"


def _macro() -> MacroBlock:
    return MacroBlock(
        items=[
            MacroItem("CPI", 0.3, "%", "2026年10月", MACRO_SOURCE),
            MacroItem("PPI", -2.1, "%", "2026年10月", MACRO_SOURCE),
            MacroItem("PMI", 49.5, "指数", "2026年10月", MACRO_SOURCE, "非制造业指数 50.1"),
            MacroItem("社零", 2.9, "%", "2026年10月", MACRO_SOURCE),
            MacroItem("固定资产投资", 10.0, "%", "2026年10月", MACRO_SOURCE),
            MacroItem("进出口", 5.4, "%", "2026年10月", MACRO_SOURCE, "进口同比 1.2%"),
        ]
    )


def _valuation() -> Valuation:
    return Valuation(
        pe_ttm=12.6,
        pe_percentile=45.2,
        percentile_window=120,
        pe_date="2026-11-01",
        official_pe1=13.61,
        official_pe2=14.69,
        official_div1=2.6,
        official_div2=2.5,
        official_date="2026-11-26",
        source=f"{PE_SOURCE} / {OFFICIAL_SOURCE}",
    )


def _margin() -> Margin:
    return Margin(
        sh=100.0,
        sz=50.0,
        total=150.0,
        change_5d=10.0,
        as_of="2026-11-25",
        source="上交所/深交所（akshare）",
    )


def _earnings() -> Earnings:
    return Earnings(
        period="2026-09-30",
        net_profit_yoy=100.0,
        revenue_yoy=25.0,
        coverage=1 / 3,
        covered=1,
        total=3,
        coverage_low=True,
        source="东财业绩报表（akshare）",
        note="按个股财报加权聚合，非官方指数口径",
    )


def _fundamentals() -> Fundamentals:
    return Fundamentals(
        macro=_macro(), valuation=_valuation(), margin=_margin(), earnings=_earnings()
    )


def _facts(fundamentals=None) -> MarketFacts:
    return MarketFacts(trade_date=DAY, fundamentals=fundamentals)


def _headings(report: str) -> list[str]:
    return [line for line in report.splitlines() if line.startswith("## ")]


def _section(report: str, heading: str) -> str:
    after = report.split(f"## {heading}\n\n", 1)[1]
    return after.split("\n\n## ", 1)[0]


def test_default_report_stays_seven_sections():
    assert _headings(render_market(_facts(), Summary(""))) == [
        "## 结论",
        "## 指数趋势",
        "## 两市成交额",
        "## 市场情绪",
        "## 行业强弱",
        "## 新闻与政策",
        "## 数据缺口",
    ]


def test_fundamentals_insert_four_sections_before_the_gaps():
    assert _headings(render_market(_facts(_fundamentals()), Summary(""))) == [
        "## 结论",
        "## 指数趋势",
        "## 两市成交额",
        "## 市场情绪",
        "## 行业强弱",
        "## 新闻与政策",
        "## 宏观基本面",
        "## 估值水平",
        "## 资金面",
        "## 盈利概览",
        "## 数据缺口",
    ]


def test_macro_table_lists_value_unit_period_and_source():
    section = _section(render_market(_facts(_fundamentals()), Summary("")), "宏观基本面")

    assert "| 指标 | 数值 | 单位 | 统计期 | 来源 |" in section
    assert f"| CPI | 0.30 | % | 2026年10月 | {MACRO_SOURCE} |" in section
    assert f"| PMI | 49.50 | 指数 | 2026年10月 | {MACRO_SOURCE} |" in section
    assert "- PMI：非制造业指数 50.1" in section


def test_macro_missing_item_renders_unavailable_and_adds_gap():
    macro = _macro()
    macro.items[0] = MacroItem("CPI", None, "%", None, MACRO_SOURCE)
    factors = Fundamentals(macro=macro)

    section = _section(render_market(_facts(factors), Summary("")), "宏观基本面")

    assert f"| CPI | 不可用 | % | 不可用 | {MACRO_SOURCE} |" in section
    assert f"| PPI | -2.10 | % | 2026年10月 | {MACRO_SOURCE} |" in section
    gaps = collect_gaps([], None, None, None, None, fundamentals=factors)
    assert "macro: CPI 不可用" in gaps


def test_valuation_renders_third_party_and_official_side_by_side():
    section = _section(render_market(_facts(_fundamentals()), Summary("")), "估值水平")

    assert "第三方 PE(TTM)：12.60｜日期：2026-11-01" in section
    assert "PE 分位：45.2%（近 120 个月）" in section
    assert "官方市盈率1：13.61" in section
    assert "官方市盈率2：14.69" in section
    assert "官方股息率1：2.60%" in section
    assert "官方股息率2：2.50%" in section
    assert "官方日期：2026-11-26" in section
    assert f"来源：{PE_SOURCE} / {OFFICIAL_SOURCE}" in section
    assert "口径以中证指数为准" in section


def test_valuation_without_official_values_names_only_the_third_party_source():
    valuation = Valuation(
        pe_ttm=12.6,
        pe_percentile=50.0,
        percentile_window=36,
        pe_date="2026-11-01",
        source=PE_SOURCE,
    )
    factors = Fundamentals(valuation=valuation)

    section = _section(render_market(_facts(factors), Summary("")), "估值水平")

    assert "PE 分位：50.0%（近 36 个月）" in section
    assert "官方市盈率1：不可用" in section
    assert f"来源：{PE_SOURCE}" in section.splitlines()
    assert f"来源：{PE_SOURCE} / {OFFICIAL_SOURCE}" not in section
    gaps = collect_gaps([], None, None, None, None, fundamentals=factors)
    assert "valuation: 中证官方估值不可用" in gaps


def test_margin_single_market_leaves_total_and_change_unavailable():
    margin = Margin(
        sh=100.0,
        as_of="2026-11-25",
        source="上交所（akshare）",
        note="仅沪市数据可用，合计与 5 日变化不可用",
    )
    factors = Fundamentals(margin=margin)

    section = _section(render_market(_facts(factors), Summary("")), "资金面")

    assert "沪市：100.00 亿元" in section
    assert "深市：不可用" in section
    assert "合计：不可用" in section
    assert "5 日变化：不可用" in section
    assert "不可用 亿元" not in section
    assert "As of：2026-11-25" in section
    assert "说明：仅沪市数据可用，合计与 5 日变化不可用" in section


def test_margin_lag_reports_actual_as_of_and_five_day_change():
    margin = Margin(
        sh=100.0,
        sz=50.0,
        total=150.0,
        change_5d=-10.0,
        as_of="2026-11-05",
        source="上交所/深交所（akshare）",
    )

    section = _section(render_market(_facts(Fundamentals(margin=margin)), Summary("")), "资金面")

    assert "合计：150.00 亿元" in section
    assert "5 日变化：-10.00 亿元" in section
    assert "As of：2026-11-05" in section
    assert "2026-11-26" not in section


def test_earnings_renders_period_growth_coverage_and_low_coverage():
    section = _section(render_market(_facts(_fundamentals()), Summary("")), "盈利概览")

    assert "报告期：2026-09-30" in section
    assert "净利润同比：+100.00%" in section
    assert "营收同比：+25.00%" in section
    assert "覆盖：1/3（33.3%），覆盖不足" in section
    assert "说明：按个股财报加权聚合，非官方指数口径" in section


def test_earnings_without_profit_yoy_is_unavailable_and_adds_gap():
    earnings = Earnings(
        period="2026-09-30",
        net_profit_yoy=None,
        revenue_yoy=None,
        coverage=0.0,
        covered=0,
        total=10,
        coverage_low=True,
    )
    factors = Fundamentals(earnings=earnings)

    report = render_market(_facts(factors), Summary(""))

    section = _section(report, "盈利概览")
    assert section == "数据不可用"
    assert "报告期" not in section
    gaps = collect_gaps([], None, None, None, None, fundamentals=factors)
    assert "earnings: 盈利数据不可用" in gaps


def test_history_mode_shows_only_the_reason_in_each_section():
    report = render_market(
        _facts(Fundamentals(unavailable="历史模式不可用")), Summary("")
    )

    for heading in ("宏观基本面", "估值水平", "资金面", "盈利概览"):
        assert _section(report, heading) == "历史模式不可用"
