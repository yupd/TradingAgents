import inspect
from pathlib import Path

from tradingagents.dataflows.vendors.a_share.patterns import detect_patterns
from tradingagents.dataflows.vendors.a_share.types import DailyBar


def _bar(date, o, h, l, c):
    return DailyBar(date=date, open=o, high=h, low=l, close=c,
                    volume=1000, source="test", as_of=date)


def _series(closes):
    return [_bar(f"2026-11-{i + 1:02d}", c, c * 1.01, c * 0.99, c)
            for i, c in enumerate(closes)]


def _rules(bars):
    return {hit.rule for hit in detect_patterns(bars).hits}


def test_pattern_hit_exposes_designed_fields():
    from tradingagents.dataflows.vendors.a_share.patterns import PatternHit

    hit = PatternHit(
        date="2026-11-20",
        pattern="十字星",
        rule="DOJI",
        direction="中性",
        bars=(),
        detail="实体 0.01 / 全幅 1.00（<=5%）",
    )
    assert (hit.date, hit.pattern, hit.rule, hit.direction) == (
        "2026-11-20", "十字星", "DOJI", "中性")
    assert hit.bars == () and "5%" in hit.detail


def test_patterns_module_does_not_import_pandas():
    import tradingagents.dataflows.vendors.a_share.patterns as patterns

    source = Path(inspect.getfile(patterns)).read_text()
    assert "pandas" not in source


def test_doji_is_detected_and_wide_body_is_not():
    doji = _bar("2026-11-20", 10.0, 10.5, 9.5, 10.01)
    wide = _bar("2026-11-20", 10.0, 10.5, 9.5, 10.2)
    assert "DOJI" in _rules([doji])
    assert "DOJI" not in _rules([wide])


def test_hammer_needs_downtrend():
    bars = _series([10.0, 9.8, 9.6, 9.4, 9.2, 9.0]) + [
        _bar("2026-11-07", 9.2, 9.35, 8.5, 9.3)]
    rules = _rules(bars)
    assert "HAMMER" in rules
    assert "HANGING_MAN" not in rules


def test_hammer_shape_in_uptrend_is_hanging_man():
    bars = _series([8.0, 8.2, 8.4, 8.6, 8.8, 9.0]) + [
        _bar("2026-11-07", 9.2, 9.35, 8.5, 9.3)]
    rules = _rules(bars)
    assert "HANGING_MAN" in rules
    assert "HAMMER" not in rules


def test_hammer_shape_with_flat_trend_is_not_reported():
    bars = _series([10.0] * 6) + [_bar("2026-11-07", 9.2, 9.35, 8.5, 9.3)]
    rules = _rules(bars)
    assert "HAMMER" not in rules and "HANGING_MAN" not in rules


def test_shooting_star_needs_uptrend():
    bars = _series([8.0, 8.2, 8.4, 8.6, 8.8, 9.0]) + [
        _bar("2026-11-07", 9.0, 9.7, 8.85, 8.9)]
    assert "SHOOTING_STAR" in _rules(bars)

    down = _series([10.0, 9.8, 9.6, 9.4, 9.2, 9.0]) + [
        _bar("2026-11-07", 9.0, 9.7, 8.85, 8.9)]
    assert "SHOOTING_STAR" not in _rules(down)


def test_bullish_engulfing_detected_and_partial_body_rejected():
    prev = _bar("2026-11-19", 12.0, 12.1, 11.4, 11.5)
    hit = _bar("2026-11-20", 11.4, 12.2, 11.3, 12.1)
    assert "BULLISH_ENGULFING" in _rules([prev, hit])

    partial = _bar("2026-11-20", 11.4, 12.0, 11.3, 11.9)
    assert "BULLISH_ENGULFING" not in _rules([prev, partial])


def test_bearish_engulfing_detected():
    prev = _bar("2026-11-19", 10.0, 10.6, 9.9, 10.5)
    hit = _bar("2026-11-20", 10.6, 10.7, 9.8, 9.9)
    assert "BEARISH_ENGULFING" in _rules([prev, hit])


def test_morning_star_detected_and_short_third_rejected():
    first = _bar("2026-11-18", 12.0, 12.1, 10.9, 11.0)
    second = _bar("2026-11-19", 11.0, 11.05, 10.75, 10.95)
    third = _bar("2026-11-20", 10.95, 11.7, 10.9, 11.6)
    assert "MORNING_STAR" in _rules([first, second, third])

    weak = _bar("2026-11-20", 10.95, 11.4, 10.9, 11.3)
    assert "MORNING_STAR" not in _rules([first, second, weak])


def test_evening_star_detected():
    first = _bar("2026-11-18", 10.0, 11.1, 9.9, 11.0)
    second = _bar("2026-11-19", 11.0, 11.2, 10.9, 11.05)
    third = _bar("2026-11-20", 11.05, 11.1, 10.3, 10.4)
    assert "EVENING_STAR" in _rules([first, second, third])


def test_limit_up_one_price_bar_has_no_pattern():
    flat = _bar("2026-11-20", 10.0, 10.0, 10.0, 10.0)
    scan = detect_patterns([flat])
    assert scan.hits == ()


def test_short_history_reports_skipped_trend_rules():
    bars = _series([10.0] * 4) + [_bar("2026-11-05", 9.2, 9.35, 8.5, 9.3)]
    scan = detect_patterns(bars)
    assert "HAMMER" not in {hit.rule for hit in scan.hits}
    assert scan.skipped == ("HAMMER", "HANGING_MAN", "SHOOTING_STAR")


def test_single_bar_skips_every_multi_bar_rule():
    scan = detect_patterns([_bar("2026-11-20", 10.0, 10.5, 9.5, 10.01)])
    assert scan.skipped == (
        "HAMMER", "HANGING_MAN", "SHOOTING_STAR",
        "BULLISH_ENGULFING", "BEARISH_ENGULFING",
        "MORNING_STAR", "EVENING_STAR")


def test_same_day_hits_are_ordered_and_repeatable():
    bars = _series([10.0, 9.8, 9.6, 9.4, 9.2, 9.0]) + [
        _bar("2026-11-07", 9.0, 9.1, 8.1, 9.01)]
    first = detect_patterns(bars)
    second = detect_patterns(bars)
    assert first == second
    dates = [hit.date for hit in first.hits]
    assert dates == sorted(dates, reverse=True)
    assert [hit.rule for hit in first.hits if hit.date == "2026-11-07"] == [
        "DOJI", "HAMMER"]


def test_format_patterns_table_and_footer():
    from tradingagents.dataflows.vendors.a_share.format import format_patterns
    from tradingagents.dataflows.vendors.a_share.patterns import PatternHit
    from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

    hit = PatternHit(
        date="2026-11-20", pattern="十字星", rule="DOJI", direction="中性",
        bars=(), detail="开10.00 高10.50 低9.50 收10.01；实体 0.01 / 全幅 1.00（<=5%）")
    text = format_patterns(parse_ashare("600519"), (hit,), "mootdx", "2026-11-21", 60)
    assert "| 日期 | 形态 | 方向 | 规则 | 依据 |" in text
    assert "| 2026-11-20 | 十字星 | 中性 | DOJI |" in text
    assert "Source: mootdx | As of: 2026-11-21 | 窗口：60 根" in text


def test_format_patterns_reports_empty_window_and_skipped_rules():
    from tradingagents.dataflows.vendors.a_share.format import format_patterns
    from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

    text = format_patterns(
        parse_ashare("600519"), (), "mootdx", "2026-11-21", 5,
        ("HAMMER", "HANGING_MAN", "SHOOTING_STAR"))
    assert "未检测到匹配形态" in text
    assert "Source: mootdx" in text
    assert "历史不足，已跳过：锤子线、上吊线、射击之星" in text


def test_zero_prior_close_does_not_crash():
    bars = [
        _bar("2026-11-01", 0.0, 0.0, 0.0, 0.0),
        _bar("2026-11-02", 10.0, 10.1, 9.9, 10.0),
        _bar("2026-11-03", 9.8, 9.9, 9.7, 9.8),
        _bar("2026-11-04", 9.6, 9.7, 9.5, 9.6),
        _bar("2026-11-05", 9.4, 9.5, 9.3, 9.4),
        _bar("2026-11-06", 9.2, 9.3, 9.1, 9.2),
        _bar("2026-11-07", 9.2, 9.35, 8.5, 9.3),
    ]
    scan = detect_patterns(bars)
    assert isinstance(scan.hits, tuple)


def test_engulfing_detail_lists_both_dates():
    prev = _bar("2026-11-19", 12.0, 12.1, 11.4, 11.5)
    hit = _bar("2026-11-20", 11.4, 12.2, 11.3, 12.1)
    detail = next(h.detail for h in detect_patterns([prev, hit]).hits
                  if h.rule == "BULLISH_ENGULFING")
    assert "2026-11-19" in detail and "2026-11-20" in detail


def test_star_detail_lists_three_dates():
    first = _bar("2026-11-18", 12.0, 12.1, 10.9, 11.0)
    second = _bar("2026-11-19", 11.0, 11.05, 10.75, 10.95)
    third = _bar("2026-11-20", 10.95, 11.7, 10.9, 11.6)
    detail = next(h.detail for h in detect_patterns([first, second, third]).hits
                  if h.rule == "MORNING_STAR")
    for date in ("2026-11-18", "2026-11-19", "2026-11-20"):
        assert date in detail
