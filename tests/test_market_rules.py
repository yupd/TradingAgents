"""Unit tests for the multi-period index metrics in ``market.rules``."""

from dataclasses import replace

import pytest

from market.fetch import IndexQuote, IndexSpec, Industries, NewsResult, Sentiment, Turnover
from market.rules import (
    Flag,
    Trend,
    broken_rate,
    build_index_quote,
    classify_trend,
    collect_gaps,
    compute_flags,
    resolve_trade_date,
)
from tradingagents.dataflows.vendors.a_share.types import DailyBar

SPEC = IndexSpec(name="上证", code="sh000001", exchange="SH")


def _bars(count: int, source: str = "tencent") -> list[DailyBar]:
    """``count`` bars whose close is 100+i and volume is 1000+i."""
    date = "2026-10-{:02d}"
    return [
        DailyBar(
            date=date.format(i + 1),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.0 + i,
            volume=1000.0 + i,
            source=source,
            as_of=date.format(i + 1),
        )
        for i in range(count)
    ]


def test_build_index_quote_uses_expected_windows():
    bars = _bars(100)
    quote = build_index_quote(SPEC, bars)

    assert quote.name == "上证"
    assert quote.code == "sh000001"
    assert quote.source == "tencent"
    assert quote.as_of == bars[-1].as_of
    assert quote.close == pytest.approx(199.0)
    # Latest close vs the previous close.
    assert quote.change_pct == pytest.approx((199 / 198 - 1) * 100)
    # closes[-6], closes[-21] and closes[-61] are 194, 179 and 139.
    assert quote.return_5d == pytest.approx((199 / 194 - 1) * 100)
    assert quote.return_20d == pytest.approx((199 / 179 - 1) * 100)
    assert quote.return_60d == pytest.approx((199 / 139 - 1) * 100)
    # Means of closes 180..199 and 140..199.
    assert quote.ma20 == pytest.approx(189.5)
    assert quote.ma60 == pytest.approx(169.5)
    # Today's volume over the 20 sessions before it (1079..1098).
    assert quote.volume_ratio == pytest.approx(1099 / 1088.5)


def test_build_index_quote_window_edges():
    at_six = build_index_quote(SPEC, _bars(6))
    assert at_six.return_5d == pytest.approx((105 / 100 - 1) * 100)
    assert at_six.return_20d is None

    at_twenty = build_index_quote(SPEC, _bars(20))
    assert at_twenty.ma20 == pytest.approx(sum(range(100, 120)) / 20)
    assert at_twenty.return_20d is None
    assert at_twenty.volume_ratio is None

    at_twenty_one = build_index_quote(SPEC, _bars(21))
    assert at_twenty_one.return_20d == pytest.approx((120 / 100 - 1) * 100)
    assert at_twenty_one.ma20 == pytest.approx(sum(range(101, 121)) / 20)
    assert at_twenty_one.volume_ratio == pytest.approx(
        1020 / (sum(range(1000, 1020)) / 20)
    )
    assert at_twenty_one.ma60 is None

    at_sixty = build_index_quote(SPEC, _bars(60))
    assert at_sixty.ma60 == pytest.approx(sum(range(100, 160)) / 60)
    assert at_sixty.return_60d is None

    at_sixty_one = build_index_quote(SPEC, _bars(61))
    assert at_sixty_one.return_60d == pytest.approx((160 / 100 - 1) * 100)


def test_build_index_quote_at_thirty_bars_omits_sixty_day_windows():
    quote = build_index_quote(SPEC, _bars(30))

    assert quote.return_60d is None
    assert quote.ma60 is None
    assert quote.change_pct == pytest.approx((129 / 128 - 1) * 100)
    assert quote.return_5d == pytest.approx((129 / 124 - 1) * 100)
    assert quote.return_20d == pytest.approx((129 / 109 - 1) * 100)
    assert quote.ma20 == pytest.approx(119.5)
    assert quote.volume_ratio == pytest.approx(1029 / 1018.5)


def test_build_index_quote_zero_volume_baseline_yields_none():
    bars = [replace(bar, volume=0.0) for bar in _bars(21)[:-1]]
    bars.append(replace(_bars(21)[-1], volume=1000.0))

    quote = build_index_quote(SPEC, bars)

    assert quote.volume_ratio is None


def test_build_index_quote_leaves_unavailable_windows_none():
    quote = build_index_quote(SPEC, _bars(5))

    assert quote.close == pytest.approx(104.0)
    assert quote.change_pct == pytest.approx((104 / 103 - 1) * 100)
    assert quote.return_5d is None
    assert quote.return_20d is None
    assert quote.return_60d is None
    assert quote.ma20 is None
    assert quote.ma60 is None
    assert quote.volume_ratio is None


def test_build_index_quote_with_no_bars():
    quote = build_index_quote(SPEC, [])

    assert quote.name == "上证"
    assert quote.code == "sh000001"
    assert quote.close is None
    assert quote.change_pct is None


def test_resolve_trade_date_normalizes_to_previous_day(monkeypatch):
    monkeypatch.setattr("market.rules.previous_trade_date", lambda value: "2026-11-25")

    assert resolve_trade_date("2026-11-26") == ("2026-11-25", None)


def test_resolve_trade_date_calendar_failure_keeps_request(monkeypatch):
    def boom(value):
        raise RuntimeError("calendar offline")

    monkeypatch.setattr("market.rules.previous_trade_date", boom)

    normalized, gap = resolve_trade_date("2026-11-26")

    assert normalized == "2026-11-26"
    assert "calendar" in gap


def test_resolve_trade_date_defaults_to_today(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "market.rules.previous_trade_date", lambda value: seen.append(value) or value
    )

    assert resolve_trade_date(requested=None, today="2026-11-26") == ("2026-11-26", None)
    assert seen == ["2026-11-26"]


def test_resolve_trade_date_rejects_invalid_format():
    with pytest.raises(ValueError):
        resolve_trade_date("2026/11/26")


@pytest.mark.parametrize("requested", ["", "   "])
def test_resolve_trade_date_rejects_blank_requested(requested):
    with pytest.raises(ValueError):
        resolve_trade_date(requested)


def test_resolve_trade_date_rejects_unpadded_parts(monkeypatch):
    monkeypatch.setattr("market.rules.previous_trade_date", lambda value: value)

    with pytest.raises(ValueError):
        resolve_trade_date("2026-1-1")
    # A fully padded date still normalizes as before.
    assert resolve_trade_date("2026-11-26") == ("2026-11-26", None)


def test_broken_rate_normal():
    assert broken_rate(70, 30) == pytest.approx(30.0)


def test_broken_rate_no_limit_up():
    assert broken_rate(0, 0) is None


def test_broken_rate_missing_input():
    assert broken_rate(None, 30) is None
    assert broken_rate(70, None) is None


def test_broken_rate_zero_broken():
    assert broken_rate(3, 0) == pytest.approx(0.0)


def _full_gap_inputs():
    """Everything present: one quote, both turnover sides, all sentiment pools."""
    indices = [IndexQuote(name="上证", code="sh000001", close=3000.0)]
    turnover = Turnover(sh=4000.0, sz=7314.446)
    sentiment = Sentiment(limit_up=50, broken=6, limit_down=2)
    industries = Industries(gainers=[], losers=[], as_of="2026-11-26")
    return indices, turnover, sentiment, industries, NewsResult([])


def test_collect_gaps_empty_when_all_present():
    assert collect_gaps(*_full_gap_inputs()) == []


def test_collect_gaps_lists_each_missing_item():
    _, _, sentiment, industries, _ = _full_gap_inputs()
    indices = [IndexQuote(name="上证", code="sh000001")]
    turnover = Turnover(sh=None, sz=7314.446)
    news = NewsResult([], gap="news: 无可用条目")

    assert collect_gaps(indices, turnover, sentiment, industries, news) == [
        "indices: 上证 取数失败",
        "turnover: 沪市成交额不可用",
        "news: 无可用条目",
    ]


@pytest.mark.parametrize("note", ["仅当日，历史不可用", "行业榜无数据"])
def test_collect_gaps_keeps_industries_note(note):
    indices, turnover, sentiment, _, news = _full_gap_inputs()
    industries = Industries(gainers=[], losers=[], as_of="2026-11-26", note=note)

    assert collect_gaps(indices, turnover, sentiment, industries, news) == [
        f"industries: {note}"
    ]


def test_collect_gaps_deduplicates_extra():
    indices, turnover, sentiment, industries, news = _full_gap_inputs()

    assert collect_gaps(
        indices, turnover, sentiment, industries, news, extra=["a", "a", "b"]
    ) == ["a", "b"]


def test_collect_gaps_whole_source_missing():
    indices, _, _, _, news = _full_gap_inputs()

    assert collect_gaps(indices, None, None, None, news) == [
        "turnover: 成交额不可用",
        "sentiment: 情绪数据不可用",
        "industries: 行业榜不可用",
    ]


def _hs300(close=110.0, ma20=105.0, ma60=100.0, return_20d=5.0) -> IndexQuote:
    return IndexQuote(
        name="沪深300",
        code="sh000300",
        close=close,
        ma20=ma20,
        ma60=ma60,
        return_20d=return_20d,
    )


def test_classify_trend_up():
    assert classify_trend(_hs300()) == Trend("上行", True, True, True)


def test_classify_trend_down():
    assert classify_trend(
        _hs300(close=100.0, ma20=105.0, ma60=110.0, return_20d=-5.0)
    ) == Trend("下行", False, False, False)


def test_classify_trend_sideways():
    # Only the 20-day return flips.
    assert classify_trend(_hs300(return_20d=-1.0)) == Trend("震荡", True, True, False)


def test_classify_trend_tie_is_sideways():
    # close == ma20 is not "above", so neither 上行 nor 下行.
    assert classify_trend(_hs300(close=105.0)) == Trend("震荡", False, True, True)


def test_classify_trend_all_equal_is_sideways():
    # Equality fails the strict "<" down conditions too, so it stays 震荡.
    assert classify_trend(
        _hs300(close=100.0, ma20=100.0, ma60=100.0, return_20d=0.0)
    ) == Trend("震荡", False, False, False)


@pytest.mark.parametrize("missing", ["close", "ma20", "ma60", "return_20d"])
def test_classify_trend_undetermined(missing):
    quote = replace(_hs300(), **{missing: None})

    assert classify_trend(quote) == Trend("无法判定", None, None, None)


def _quote(name="上证", code="sh000001", return_20d=None, volume_ratio=None) -> IndexQuote:
    return IndexQuote(
        name=name,
        code=code,
        return_20d=return_20d,
        volume_ratio=volume_ratio,
    )


@pytest.mark.parametrize("ratio", [1.19, 0.81])
def test_compute_flags_volume_inside_band_is_silent(ratio):
    indices = [_quote(name="沪深300", code="sh000300", volume_ratio=ratio)]

    assert compute_flags(indices, None) == []


def test_compute_flags_volume_up_at_boundary():
    indices = [_quote(name="沪深300", code="sh000300", volume_ratio=1.2)]

    assert compute_flags(indices, None) == [
        Flag("volume_up", "放量", "沪深300 20 日量能倍数 1.2")
    ]


def test_compute_flags_volume_down_at_boundary():
    indices = [_quote(name="沪深300", code="sh000300", volume_ratio=0.8)]

    assert compute_flags(indices, None) == [
        Flag("volume_down", "缩量", "沪深300 20 日量能倍数 0.8")
    ]


def test_compute_flags_volume_ignores_non_hs300_quote():
    indices = [_quote(name="上证", code="sh000001", volume_ratio=1.5)]

    assert compute_flags(indices, None) == []


def test_compute_flags_limit_ratio_counts():
    sentiment = Sentiment(limit_up=50, limit_down=3)

    flags = compute_flags([], sentiment)

    assert flags == [Flag("limit_ratio", "涨停/跌停", "涨停 50 / 跌停 3")]


@pytest.mark.parametrize("missing", ["limit_up", "limit_down"])
def test_compute_flags_limit_ratio_missing_count_skips(missing):
    sentiment = Sentiment(**{"limit_up": 50, "limit_down": 3, missing: None})

    assert compute_flags([], sentiment) == []


def test_compute_flags_broken_rate_skips_none():
    sentiment = Sentiment(broken_rate=None)

    assert compute_flags([], sentiment) == []


def test_compute_flags_broken_rate_value():
    sentiment = Sentiment(broken_rate=30.0)

    assert compute_flags([], sentiment) == [Flag("broken_rate", "炸板率", "30.0%")]


def test_compute_flags_dispersion_names_extremes():
    indices = [
        _quote(name="深成", code="sz399001", return_20d=-2.0),
        _quote(name="上证", code="sh000001", return_20d=0.0),
        _quote(name="创业板", code="sz399006", return_20d=3.5),
    ]

    assert compute_flags(indices, None) == [
        Flag(
            "dispersion",
            "指数 20 日分化",
            "极差 5.5 个百分点（最强 创业板 +3.5%，最弱 深成 -2.0%）",
        )
    ]


def test_compute_flags_dispersion_needs_two_returns():
    indices = [
        _quote(name="深成", code="sz399001", return_20d=-2.0),
        _quote(name="上证", code="sh000001", return_20d=None),
    ]

    assert compute_flags(indices, None) == []
