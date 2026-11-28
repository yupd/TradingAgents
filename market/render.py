"""One Markdown file for the day's market trend report."""

from __future__ import annotations

from market.fetch import MarketFacts
from market.summarize import Summary

_NA = "不可用"
_UNAVAILABLE = "数据不可用"

_HEADINGS = (
    "结论",
    "指数趋势",
    "两市成交额",
    "市场情绪",
    "行业强弱",
    "新闻与政策",
    "数据缺口",
)

_FUNDAMENTAL_HEADINGS = ("宏观基本面", "估值水平", "资金面", "盈利概览")
_HISTORY = "历史模式不可用"

_INDEX_COLUMNS = (
    "指数",
    "收盘",
    "当日",
    "5日",
    "20日",
    "60日",
    "MA20",
    "MA60",
    "20日量能倍数",
)


def _num(value: float | None, pattern: str = "{:.2f}") -> str:
    return _NA if value is None else pattern.format(value)


def _pct(value: float | None) -> str:
    return _num(value, "{:+.2f}%")


def _count(value: int | None) -> str:
    return _NA if value is None else str(value)


def _rate(value: float | None) -> str:
    return _NA if value is None else f"{value:.1f}%"


def _join(values) -> str:
    unique = list(dict.fromkeys(value for value in values if value))
    return "、".join(unique) if unique else _NA


def _table(header, rows) -> str:
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _yes_no(value: bool | None) -> str:
    return _NA if value is None else ("是" if value else "否")


def _conclusion(facts: MarketFacts, summary: Summary) -> str:
    trend = getattr(facts.trend, "level", None) or "无法判定"
    decision = facts.trend
    lines = [
        f"趋势：{trend}",
        f"收盘>MA20：{_yes_no(getattr(decision, 'close_above_ma20', None))}",
        f"MA20>MA60：{_yes_no(getattr(decision, 'ma20_above_ma60', None))}",
        f"20日涨跌>0：{_yes_no(getattr(decision, 'return_20d_positive', None))}",
    ]
    if summary.text:
        lines.append(summary.text)
    lines.extend(f"- {flag.label}：{flag.detail}" for flag in facts.flags)
    if summary.dropped > 0:
        lines.append(f"（已丢弃 {summary.dropped} 句模型输出，含未提供数字）")
    return "\n".join(lines)


def _indices(facts: MarketFacts) -> str:
    if not facts.indices:
        return _UNAVAILABLE
    rows = [
        [
            quote.name,
            _num(quote.close),
            _pct(quote.change_pct),
            _pct(quote.return_5d),
            _pct(quote.return_20d),
            _pct(quote.return_60d),
            _num(quote.ma20),
            _num(quote.ma60),
            _num(quote.volume_ratio),
        ]
        for quote in facts.indices
    ]
    return "\n".join(
        [
            _table(_INDEX_COLUMNS, rows),
            "",
            "20日量能倍数按指数成交量计算（指数成交量口径）",
            "",
            f"来源：{_join(quote.source for quote in facts.indices)} | "
            f"As of: {_join(quote.as_of for quote in facts.indices)}",
        ]
    )


def _turnover(turnover) -> str:
    sh = turnover.sh if turnover else None
    sz = turnover.sz if turnover else None
    total = turnover.total if turnover else None
    rows = [
        ["沪市", _num(sh, "{:.2f} 亿元")],
        ["深市", _num(sz, "{:.2f} 亿元")],
        ["合计", _num(total, "{:.2f} 亿元")],
    ]
    lines = [_table(("指标", "数值"), rows), ""]
    if turnover and turnover.note:
        lines += [f"说明：{turnover.note}", ""]
    source = turnover.source if turnover and turnover.source else _NA
    as_of = turnover.as_of if turnover and turnover.as_of else _NA
    lines.append(f"来源：{source} | As of: {as_of}")
    return "\n".join(lines)


def _sentiment(sentiment) -> str:
    limit_up = sentiment.limit_up if sentiment else None
    limit_down = sentiment.limit_down if sentiment else None
    broken = sentiment.broken if sentiment else None
    broken_rate = sentiment.broken_rate if sentiment else None
    max_streak = sentiment.max_streak if sentiment else None
    line = (
        f"涨停 {_count(limit_up)} / 跌停 {_count(limit_down)} / 炸板 {_count(broken)}；"
        f"炸板率 {_rate(broken_rate)}；最高连板 {_count(max_streak)}"
    )
    source = sentiment.source if sentiment and sentiment.source else _NA
    as_of = sentiment.as_of if sentiment and sentiment.as_of else _NA
    return "\n".join([line, "", f"来源：{source} | As of: {as_of}"])


def _industry_line(label: str, rows) -> str:
    if not rows:
        return f"{label}：{_UNAVAILABLE}"
    items = " ".join(f"{name} {value:+.1f}%" for name, value in rows)
    return f"{label}：{items}"


def _industries(industries) -> str:
    losers = industries.losers if industries else []
    if not losers or all(value < 0 for _, value in losers):
        loser_label = "跌幅前5"
    elif all(value >= 0 for _, value in losers):
        loser_label = "涨幅后5"
    else:
        loser_label = "涨跌幅后5"
    lines = [
        _industry_line("涨幅前5", industries.gainers if industries else []),
        _industry_line(loser_label, losers),
    ]
    if industries and industries.note:
        lines.append(f"说明：{industries.note}")
    source = industries.source if industries and industries.source else _NA
    as_of = industries.as_of if industries and industries.as_of else _NA
    lines += ["", f"来源：{source} | As of: {as_of}"]
    return "\n".join(lines)


def _news(news) -> str:
    if not news:
        return f"{_UNAVAILABLE}\n\n来源：东财快讯 | As of: {_NA}"
    return "\n".join(
        f"- [{item.source} {item.published_at}] {item.title}（媒体口径，未核实）"
        for item in news
    )


def _gaps(gaps: list[str]) -> str:
    return "\n".join(f"- {gap}" for gap in gaps) if gaps else "无"


def _yi(value: float | None, signed: bool = False) -> str:
    if value is None:
        return _NA
    return f"{value:+.2f} 亿元" if signed else f"{value:.2f} 亿元"


def _macro(fundamentals) -> str:
    macro = fundamentals.macro
    if macro is None or not macro.items:
        return _UNAVAILABLE
    # A table whose every value is missing is not a macro block.
    if all(item.value is None for item in macro.items):
        return _UNAVAILABLE
    rows = [
        [
            item.name,
            _num(item.value),
            item.unit or _NA,
            item.period or _NA,
            item.source or _NA,
        ]
        for item in macro.items
    ]
    lines = [_table(("指标", "数值", "单位", "统计期", "来源"), rows)]
    notes = [f"- {item.name}：{item.note}" for item in macro.items if item.note]
    if notes:
        lines += ["", *notes]
    return "\n".join(lines)


def _valuation(fundamentals) -> str:
    valuation = fundamentals.valuation
    if valuation is None:
        return _UNAVAILABLE
    # Source/date alone do not make a valuation block; at least one value must exist.
    if all(
        value is None
        for value in (
            valuation.pe_ttm,
            valuation.pe_percentile,
            valuation.official_pe1,
            valuation.official_pe2,
            valuation.official_div1,
            valuation.official_div2,
        )
    ):
        return _UNAVAILABLE
    percentile = _rate(valuation.pe_percentile)
    if valuation.percentile_window is not None:
        percentile += f"（近 {valuation.percentile_window} 个月）"
    lines = [
        "标的：沪深300",
        f"第三方 PE(TTM)：{_num(valuation.pe_ttm)}｜日期：{valuation.pe_date or _NA}",
        f"PE 分位：{percentile}",
        f"官方市盈率1：{_num(valuation.official_pe1)}",
        f"官方市盈率2：{_num(valuation.official_pe2)}",
        f"官方股息率1：{_num(valuation.official_div1, '{:.2f}%')}",
        f"官方股息率2：{_num(valuation.official_div2, '{:.2f}%')}",
        f"官方日期：{valuation.official_date or _NA}",
        f"来源：{valuation.source or _NA}",
    ]
    if any(
        value is not None
        for value in (
            valuation.official_pe1,
            valuation.official_pe2,
            valuation.official_div1,
            valuation.official_div2,
        )
    ):
        lines.append("口径以中证指数为准")
    if valuation.note:
        lines.append(f"说明：{valuation.note}")
    return "\n".join(lines)


def _margin(fundamentals) -> str:
    margin = fundamentals.margin
    if margin is None:
        return _UNAVAILABLE
    if all(
        value is None
        for value in (margin.sh, margin.sz, margin.total, margin.change_5d)
    ):
        return _UNAVAILABLE
    lines = [
        f"沪市：{_yi(margin.sh)}",
        f"深市：{_yi(margin.sz)}",
        f"合计：{_yi(margin.total)}",
        f"5 日变化：{_yi(margin.change_5d, signed=True)}",
        f"As of：{margin.as_of or _NA}",
    ]
    if margin.stale_days is not None and margin.stale_days > 3:
        lines.append(f"数据滞后：{margin.stale_days} 天")
    lines.append(f"来源：{margin.source or _NA}")
    if margin.note:
        lines.append(f"说明：{margin.note}")
    return "\n".join(lines)


def _earnings(fundamentals) -> str:
    earnings = fundamentals.earnings
    # A table without a usable profit YoY is not an earnings block.
    if earnings is None or earnings.net_profit_yoy is None:
        return _UNAVAILABLE
    if earnings.coverage is None:
        coverage = _NA
    elif earnings.covered is not None and earnings.total is not None:
        coverage = (
            f"{earnings.covered}/{earnings.total}（{earnings.coverage * 100:.1f}%）"
        )
    else:
        coverage = f"{earnings.coverage * 100:.1f}%"
    if earnings.coverage_low:
        coverage = f"{coverage}，覆盖不足"
    lines = [
        f"报告期：{earnings.period or _NA}",
        f"公告截止日：{earnings.announcement_cutoff or _NA}",
        f"净利润同比：{_pct(earnings.net_profit_yoy)}",
        f"营收同比：{_pct(earnings.revenue_yoy)}",
        f"覆盖（接口返回样本内）：{coverage}",
        f"来源：{earnings.source or _NA}",
    ]
    if earnings.note:
        lines.append(f"说明：{earnings.note}")
    return "\n".join(lines)


def _fundamental_sections(fundamentals) -> dict[str, str]:
    if fundamentals.unavailable:
        return {heading: _HISTORY for heading in _FUNDAMENTAL_HEADINGS}
    return {
        "宏观基本面": _macro(fundamentals),
        "估值水平": _valuation(fundamentals),
        "资金面": _margin(fundamentals),
        "盈利概览": _earnings(fundamentals),
    }


def render_market(facts: MarketFacts, summary: Summary) -> str:
    """The seven-section Markdown report, plus four fundamentals sections when enabled."""
    sections = {
        "结论": _conclusion(facts, summary),
        "指数趋势": _indices(facts),
        "两市成交额": _turnover(facts.turnover),
        "市场情绪": _sentiment(facts.sentiment),
        "行业强弱": _industries(facts.industries),
        "新闻与政策": _news(facts.news),
        "数据缺口": _gaps(facts.gaps),
    }
    headings = list(_HEADINGS)
    if facts.fundamentals is not None:
        sections.update(_fundamental_sections(facts.fundamentals))
        gap_index = headings.index("数据缺口")
        headings[gap_index:gap_index] = list(_FUNDAMENTAL_HEADINGS)
    lines = [
        f"# A 股大盘复盘 {facts.trade_date}",
        f"行情截止：{facts.trade_date} 15:00；行业/新闻为运行时刻快照",
    ]
    for heading in headings:
        lines += ["", f"## {heading}", "", sections[heading]]
    return "\n".join(lines).rstrip() + "\n"
