"""Deterministic candlestick pattern detection over daily bars."""

from __future__ import annotations

from dataclasses import dataclass

from .types import DailyBar

# Fixed thresholds — the single source of truth for every pattern rule.
DOJI_BODY_RATIO = 0.05
SHADOW_TO_BODY = 2.0
SMALL_SHADOW_RATIO = 0.2
LONG_BODY_RATIO = 0.6
SMALL_BODY_RATIO = 0.3
TREND_LOOKBACK = 5
TREND_THRESHOLD = 0.01

RULE_ORDER = (
    "DOJI",
    "HAMMER",
    "HANGING_MAN",
    "SHOOTING_STAR",
    "BULLISH_ENGULFING",
    "BEARISH_ENGULFING",
    "MORNING_STAR",
    "EVENING_STAR",
)

TREND_RULES = ("HAMMER", "HANGING_MAN", "SHOOTING_STAR")

PATTERN_NAMES = {
    "DOJI": "十字星",
    "HAMMER": "锤子线",
    "HANGING_MAN": "上吊线",
    "SHOOTING_STAR": "射击之星",
    "BULLISH_ENGULFING": "看涨吞没",
    "BEARISH_ENGULFING": "看跌吞没",
    "MORNING_STAR": "早晨之星",
    "EVENING_STAR": "黄昏之星",
}

PATTERN_DIRECTIONS = {
    "DOJI": "中性",
    "HAMMER": "看涨",
    "HANGING_MAN": "看跌",
    "SHOOTING_STAR": "看跌",
    "BULLISH_ENGULFING": "看涨",
    "BEARISH_ENGULFING": "看跌",
    "MORNING_STAR": "看涨",
    "EVENING_STAR": "看跌",
}


@dataclass(frozen=True)
class PatternHit:
    """One detected pattern, with the bars and numbers that triggered it."""

    date: str
    pattern: str
    rule: str
    direction: str
    bars: tuple[DailyBar, ...]
    detail: str


@dataclass(frozen=True)
class PatternScan:
    """Everything one window produced: the hits and the rules history skipped."""

    hits: tuple[PatternHit, ...]
    skipped: tuple[str, ...]


def _ohlc(bar: DailyBar) -> str:
    return (f"{bar.date} 开{bar.open:.2f} 高{bar.high:.2f} "
            f"低{bar.low:.2f} 收{bar.close:.2f}")


def _hit(rule: str, bars: list[DailyBar], detail: str) -> PatternHit:
    return PatternHit(
        date=bars[-1].date,
        pattern=PATTERN_NAMES[rule],
        rule=rule,
        direction=PATTERN_DIRECTIONS[rule],
        bars=tuple(bars),
        detail=f"{_ohlc(bars[-1])}；{detail}",
    )


def _trend_change(bars: list[DailyBar], i: int) -> float | None:
    """Return the prior 5-session return, or None when history is short or bad."""
    if i < TREND_LOOKBACK + 1:
        return None
    base = bars[i - 1 - TREND_LOOKBACK].close
    if base <= 0:  # a zero/negative close from a bad vendor row has no return
        return None
    return bars[i - 1].close / base - 1


def detect_patterns(bars: list[DailyBar]) -> PatternScan:
    """Scan bars for the fixed pattern set; same input always yields same output."""
    ordered = sorted(bars, key=lambda bar: bar.date)
    hits: list[PatternHit] = []
    skipped: list[str] = []
    if len(ordered) < 2:
        skipped += ["BULLISH_ENGULFING", "BEARISH_ENGULFING"]
    if len(ordered) < 3:
        skipped += ["MORNING_STAR", "EVENING_STAR"]
    if len(ordered) < TREND_LOOKBACK + 2:
        skipped += list(TREND_RULES)
    skipped.sort(key=RULE_ORDER.index)

    for i, bar in enumerate(ordered):
        rng = bar.high - bar.low
        if rng == 0:  # limit-up/limit-down one-price bar has no shape to read
            continue
        body = abs(bar.close - bar.open)
        upper = bar.high - max(bar.open, bar.close)
        lower = min(bar.open, bar.close) - bar.low

        if body <= DOJI_BODY_RATIO * rng:
            hits.append(_hit(
                "DOJI", [bar],
                f"实体 {body:.2f} / 全幅 {rng:.2f}（<=5%）"))

        change = _trend_change(ordered, i)
        if change is not None:
            detail = (f"下影 {lower:.2f} / 实体 {body:.2f}（>=2x），"
                      f"上影 {upper:.2f} / 全幅 {rng:.2f}（<=20%），"
                      f"前5日 {change * 100:.1f}%")
            if lower >= SHADOW_TO_BODY * body and upper <= SMALL_SHADOW_RATIO * rng:
                if change < -TREND_THRESHOLD:
                    hits.append(_hit("HAMMER", [bar], detail))
                elif change > TREND_THRESHOLD:
                    hits.append(_hit("HANGING_MAN", [bar], detail))
            star_detail = (f"上影 {upper:.2f} / 实体 {body:.2f}（>=2x），"
                           f"下影 {lower:.2f} / 全幅 {rng:.2f}（<=20%），"
                           f"前5日 {change * 100:.1f}%")
            if (upper >= SHADOW_TO_BODY * body
                    and lower <= SMALL_SHADOW_RATIO * rng
                    and change > TREND_THRESHOLD):
                hits.append(_hit("SHOOTING_STAR", [bar], star_detail))

        if i >= 1:
            prev = ordered[i - 1]
            if prev.high > prev.low:
                if (prev.close < prev.open and bar.close > bar.open
                        and bar.open <= prev.close
                        and bar.close >= prev.open):
                    hits.append(_hit(
                        "BULLISH_ENGULFING", [prev, bar],
                        f"吞没前日 {_ohlc(prev)}"))
                if (prev.close > prev.open and bar.close < bar.open
                        and bar.open >= prev.close
                        and bar.close <= prev.open):
                    hits.append(_hit(
                        "BEARISH_ENGULFING", [prev, bar],
                        f"吞没前日 {_ohlc(prev)}"))

        if i >= 2:
            first, middle = ordered[i - 2], ordered[i - 1]
            first_range = first.high - first.low
            middle_range = middle.high - middle.low
            if first_range > 0 and middle_range > 0:
                first_body = abs(first.close - first.open)
                middle_body = abs(middle.close - middle.open)
                midpoint = (first.open + first.close) / 2
                small_middle = middle_body <= SMALL_BODY_RATIO * middle_range
                if (first.close < first.open
                        and first_body >= LONG_BODY_RATIO * first_range
                        and small_middle
                        and bar.close > bar.open and bar.close >= midpoint):
                    hits.append(_hit(
                        "MORNING_STAR", [first, middle, bar],
                        f"第一根 {_ohlc(first)}，第二根 {_ohlc(middle)}，"
                        f"第三根收盘 {bar.close:.2f} >= 中点 {midpoint:.2f}"))
                if (first.close > first.open
                        and first_body >= LONG_BODY_RATIO * first_range
                        and small_middle
                        and bar.close < bar.open and bar.close <= midpoint):
                    hits.append(_hit(
                        "EVENING_STAR", [first, middle, bar],
                        f"第一根 {_ohlc(first)}，第二根 {_ohlc(middle)}，"
                        f"第三根收盘 {bar.close:.2f} <= 中点 {midpoint:.2f}"))

    hits.sort(key=lambda hit: RULE_ORDER.index(hit.rule))
    hits.sort(key=lambda hit: hit.date, reverse=True)
    return PatternScan(tuple(hits), tuple(skipped))
