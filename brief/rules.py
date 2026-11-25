"""Deterministic signals computed from the facts, never from the model."""

from __future__ import annotations

from dataclasses import dataclass

from .fetch import StockFacts


@dataclass(frozen=True)
class Flag:
    kind: str
    label: str
    detail: str


def _limit_threshold(name: str, code: str) -> float:
    if "ST" in name.upper():
        return 5.0
    if code.startswith(("300", "301", "688", "689")):
        return 20.0
    return 10.0


def compute_flags(facts: StockFacts) -> list[Flag]:
    flags: list[Flag] = []
    if facts.missing:
        flags.append(Flag("data_missing", "数据缺失", ", ".join(facts.missing)))
    quote = facts.quote
    if quote is not None:
        threshold = _limit_threshold(quote.name, facts.code)
        if quote.change_pct >= threshold:
            flags.append(Flag("limit_up", "涨停", f"涨幅 {quote.change_pct:.2f}%"))
        elif quote.change_pct <= -threshold:
            flags.append(Flag("limit_down", "跌停", f"跌幅 {quote.change_pct:.2f}%"))
        recent = [b.volume for b in facts.bars[-20:] if b.volume > 0]
        if recent:
            average = sum(recent) / len(recent)
            if average and quote.volume / average >= 2:
                flags.append(Flag("volume_spike", "放量", f"量为 20 日均量的 {quote.volume / average:.1f} 倍"))
    closes = [b.close for b in facts.bars[-20:]]
    if len(closes) >= 20:
        ma20 = sum(closes) / len(closes)
        last = closes[-1]
        if last < ma20:
            flags.append(Flag("ma20_break", "跌破 MA20", f"收盘 {last:.2f} < MA20 {ma20:.2f}"))
        elif last > ma20:
            flags.append(Flag("ma20_break", "站上 MA20", f"收盘 {last:.2f} > MA20 {ma20:.2f}"))
    peak = max((b.close for b in facts.bars), default=0)
    if peak and closes:
        drawdown = (peak - closes[-1]) / peak
        if drawdown >= 0.15:
            flags.append(Flag("drawdown", "阶段回撤", f"较 60 日高点回撤 {drawdown * 100:.1f}%"))
    if facts.lockup and "解禁" in facts.lockup and not facts.lockup.startswith(("NO_DATA", "DATA_UNAVAILABLE")):
        flags.append(Flag("unlock_soon", "临近解禁", "未来 90 天内有解禁"))
    text = " ".join(facts.announcements + facts.reports)
    if "下调" in text:
        flags.append(Flag("rating_downgrade", "评级下调", "公告或研报中出现下调表述"))
    return flags
