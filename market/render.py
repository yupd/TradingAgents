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


def _conclusion(facts: MarketFacts, summary: Summary) -> str:
    trend = getattr(facts.trend, "level", None) or "无法判定"
    lines = [f"趋势：{trend}"]
    if summary.text:
        lines.append(summary.text)
    lines.extend(f"- {flag.label}：{flag.detail}" for flag in facts.flags)
    return "\n".join(lines)


def _indices(facts: MarketFacts) -> str:
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
    as_of = turnover.as_of if turnover and turnover.as_of else _NA
    lines.append(f"来源：上交所/深交所 | As of: {as_of}")
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
    as_of = sentiment.as_of if sentiment and sentiment.as_of else _NA
    return "\n".join([line, "", f"来源：东财 | As of: {as_of}"])


def _industry_line(label: str, rows) -> str:
    if not rows:
        return f"{label}：{_UNAVAILABLE}"
    items = " ".join(f"{name} {value:+.1f}%" for name, value in rows)
    return f"{label}：{items}"


def _industries(industries) -> str:
    lines = [
        _industry_line("涨幅前5", industries.gainers if industries else []),
        _industry_line("跌幅前5", industries.losers if industries else []),
    ]
    if industries and industries.note:
        lines.append(f"说明：{industries.note}")
    as_of = industries.as_of if industries and industries.as_of else _NA
    lines += ["", f"来源：同花顺 | As of: {as_of}"]
    return "\n".join(lines)


def _news(news) -> str:
    if not news:
        return _UNAVAILABLE
    return "\n".join(
        f"- [{item.source} {item.published_at}] {item.title}（媒体口径，未核实）"
        for item in news
    )


def _gaps(gaps: list[str]) -> str:
    return "\n".join(f"- {gap}" for gap in gaps) if gaps else "无"


def render_market(facts: MarketFacts, summary: Summary) -> str:
    """The seven-section Markdown report; pure and I/O-free."""
    sections = {
        "结论": _conclusion(facts, summary),
        "指数趋势": _indices(facts),
        "两市成交额": _turnover(facts.turnover),
        "市场情绪": _sentiment(facts.sentiment),
        "行业强弱": _industries(facts.industries),
        "新闻与政策": _news(facts.news),
        "数据缺口": _gaps(facts.gaps),
    }
    lines = [
        f"# A 股大盘复盘 {facts.trade_date}",
        f"数据截止：{facts.trade_date} 15:00",
    ]
    for heading in _HEADINGS:
        lines += ["", f"## {heading}", "", sections[heading]]
    return "\n".join(lines).rstrip() + "\n"
