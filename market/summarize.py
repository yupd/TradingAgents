"""Serialize the market facts into the plain-text block handed to the model."""

from __future__ import annotations

from market.fetch import Industries, IndexQuote, MarketFacts, MarketNews, Sentiment, Turnover
from market.rules import Trend

_NA = "不可用"
_PCT = "{:+.2f}%"
_YI = "{:.2f} 亿元"


def _fmt(value: float | None, pattern: str = "{:.2f}") -> str:
    return _NA if value is None else pattern.format(value)


def _yes_no(value: bool | None) -> str:
    return _NA if value is None else ("是" if value else "否")


def _count(value: int | None) -> str:
    return _NA if value is None else str(value)


def _rate(value: float | None) -> str:
    return _NA if value is None else f"{value:.1f}%"


def _position(trend: Trend | None) -> str:
    if trend is None:
        return "趋势：无法判定"
    return "\n".join(
        [
            f"趋势：{trend.level}",
            f"收盘>MA20: {_yes_no(trend.close_above_ma20)}",
            f"MA20>MA60: {_yes_no(trend.ma20_above_ma60)}",
            f"20日涨跌>0: {_yes_no(trend.return_20d_positive)}",
        ]
    )


def _indices(indices: list[IndexQuote]) -> str:
    if not indices:
        return _NA
    return "\n".join(
        f"- {q.name} {q.code}：收盘 {_fmt(q.close)}，涨跌 {_fmt(q.change_pct, _PCT)}，"
        f"5日 {_fmt(q.return_5d, _PCT)}，20日 {_fmt(q.return_20d, _PCT)}，"
        f"60日 {_fmt(q.return_60d, _PCT)}，MA20 {_fmt(q.ma20)}，"
        f"MA60 {_fmt(q.ma60)}，量能 {_fmt(q.volume_ratio)}"
        for q in indices
    )


def _turnover(turnover: Turnover | None) -> str:
    if turnover is None:
        return _NA
    lines = [
        f"沪市：{_fmt(turnover.sh, _YI)}",
        f"深市：{_fmt(turnover.sz, _YI)}",
        f"合计：{_fmt(turnover.total, _YI)}",
    ]
    if turnover.note:
        lines.append(f"说明：{turnover.note}")
    return "\n".join(lines)


def _sentiment(sentiment: Sentiment | None) -> str:
    if sentiment is None:
        return _NA
    return "\n".join(
        [
            f"涨停：{_count(sentiment.limit_up)}",
            f"跌停：{_count(sentiment.limit_down)}",
            f"炸板：{_count(sentiment.broken)}",
            f"炸板率：{_rate(sentiment.broken_rate)}",
            f"最高连板：{_count(sentiment.max_streak)}",
        ]
    )


def _industry_line(label: str, rows: list[tuple[str, float]]) -> str:
    if not rows:
        return f"{label}：{_NA}"
    items = " ".join(f"{name} {value:+.1f}%" for name, value in rows)
    return f"{label}：{items}"


def _industries(industries: Industries | None) -> str:
    if industries is None:
        return _NA
    lines = [
        _industry_line("涨幅前5", industries.gainers),
        _industry_line("跌幅前5", industries.losers),
    ]
    if industries.note:
        lines.append(f"说明：{industries.note}")
    return "\n".join(lines)


def _news(news: list[MarketNews]) -> str:
    if not news:
        return _NA
    return "\n".join(
        f"- [{item.source} {item.published_at}] {item.title}（媒体口径，未核实）"
        for item in news
    )


def facts_block(facts: MarketFacts) -> str:
    """The fact block handed to the model; pure and I/O-free."""
    sections = [
        ("档位", _position(facts.trend)),
        ("指数", _indices(facts.indices)),
        ("成交额", _turnover(facts.turnover)),
        ("情绪", _sentiment(facts.sentiment)),
        ("行业", _industries(facts.industries)),
        ("新闻", _news(facts.news)),
    ]
    lines = [f"# 大盘事实 {facts.trade_date}"]
    lines.extend(f"## {title}\n{body}" for title, body in sections)
    return "\n\n".join(lines)
