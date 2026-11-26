from types import SimpleNamespace

import pandas as pd
import pytest

from market.fetch import (
    _parse_limit_up,
    _parse_pool_count,
    build_sentiment,
    fetch_broken_pool,
    fetch_limit_down_pool,
    fetch_limit_up,
    fetch_sentiment,
)


def _limit_up_frame(streaks=(1, 2, 4)):
    return pd.DataFrame({
        "代码": [f"60000{i}" for i in range(len(streaks))],
        "名称": [f"股票{i}" for i in range(len(streaks))],
        "涨跌幅": [10.0] * len(streaks),
        "连板数": list(streaks),
        "所属行业": ["电子"] * len(streaks),
    })


def test_parse_limit_up_returns_count_and_highest_streak():
    assert _parse_limit_up(_limit_up_frame()) == (3, 4)


def test_parse_limit_up_empty_frame_is_zero_day():
    assert _parse_limit_up(_limit_up_frame(streaks=())) == (0, None)


def test_parse_limit_up_without_streak_column_keeps_count():
    frame = _limit_up_frame().drop(columns=["连板数"])

    assert _parse_limit_up(frame) == (3, None)


def test_fetch_limit_up_passes_yyyymmdd_and_parses(monkeypatch):
    import sys

    calls = []

    def fake(date):
        calls.append(date)
        return _limit_up_frame()

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_zt_pool_em=fake))

    assert fetch_limit_up("2026-11-26") == (3, 4)
    assert calls == ["20261126"]


def _pool_frame(rows):
    return pd.DataFrame({
        "代码": [f"60000{i}" for i in range(rows)],
        "名称": [f"股票{i}" for i in range(rows)],
    })


def test_parse_pool_count_counts_rows():
    assert _parse_pool_count(_pool_frame(30)) == 30
    assert _parse_pool_count(_pool_frame(43)) == 43


def test_parse_pool_count_empty_frame_is_zero():
    assert _parse_pool_count(pd.DataFrame()) == 0


def test_fetch_pools_pass_yyyymmdd_and_parse(monkeypatch):
    import sys

    calls = []

    def broken(date):
        calls.append(("broken", date))
        return _pool_frame(30)

    def limit_down(date):
        calls.append(("limit_down", date))
        return _pool_frame(43)

    monkeypatch.setitem(
        sys.modules,
        "akshare",
        SimpleNamespace(
            stock_zt_pool_zbgc_em=broken,
            stock_zt_pool_dtgc_em=limit_down,
        ),
    )

    assert fetch_broken_pool("2026-11-26") == 30
    assert fetch_limit_down_pool("2026-11-26") == 43
    assert calls == [("broken", "20261126"), ("limit_down", "20261126")]


def test_build_sentiment_computes_broken_rate():
    sentiment = build_sentiment(70, 4, 30, 5, "2026-11-26")

    assert (sentiment.limit_up, sentiment.max_streak) == (70, 4)
    assert (sentiment.broken, sentiment.limit_down) == (30, 5)
    assert sentiment.broken_rate == pytest.approx(30.0)
    assert sentiment.as_of == "2026-11-26"
    assert sentiment.source == "东财"


def _patch_pools(monkeypatch, limit_up=(70, 4), broken=30, limit_down=5):
    monkeypatch.setattr("market.fetch.fetch_limit_up", lambda date: limit_up)
    monkeypatch.setattr("market.fetch.fetch_broken_pool", lambda date: broken)
    monkeypatch.setattr("market.fetch.fetch_limit_down_pool", lambda date: limit_down)


def test_fetch_sentiment_populates_all_pools(monkeypatch):
    _patch_pools(monkeypatch)

    sentiment = fetch_sentiment("2026-11-26")

    assert (sentiment.limit_up, sentiment.max_streak) == (70, 4)
    assert (sentiment.broken, sentiment.limit_down) == (30, 5)
    assert sentiment.broken_rate == pytest.approx(30.0)
    assert sentiment.as_of == "2026-11-26"
    assert sentiment.source == "东财"


def test_fetch_sentiment_limit_down_failure_keeps_other_pools(monkeypatch):
    _patch_pools(monkeypatch)

    def boom(date):
        raise RuntimeError("limit-down unavailable")

    monkeypatch.setattr("market.fetch.fetch_limit_down_pool", boom)

    sentiment = fetch_sentiment("2026-11-26")

    assert (sentiment.limit_up, sentiment.max_streak) == (70, 4)
    assert sentiment.broken == 30
    assert sentiment.limit_down is None
    assert sentiment.broken_rate == pytest.approx(30.0)


def test_fetch_sentiment_limit_up_failure_nulls_streak_and_rate(monkeypatch):
    _patch_pools(monkeypatch)

    def boom(date):
        raise RuntimeError("limit-up unavailable")

    monkeypatch.setattr("market.fetch.fetch_limit_up", boom)

    sentiment = fetch_sentiment("2026-11-26")

    assert sentiment.limit_up is None
    assert sentiment.max_streak is None
    assert (sentiment.broken, sentiment.limit_down) == (30, 5)
    assert sentiment.broken_rate is None


def test_fetch_sentiment_all_pools_fail_returns_empty_record(monkeypatch):
    def boom(date):
        raise RuntimeError("unavailable")

    monkeypatch.setattr("market.fetch.fetch_limit_up", boom)
    monkeypatch.setattr("market.fetch.fetch_broken_pool", boom)
    monkeypatch.setattr("market.fetch.fetch_limit_down_pool", boom)

    sentiment = fetch_sentiment("2026-11-26")

    assert (sentiment.limit_up, sentiment.max_streak) == (None, None)
    assert (sentiment.broken, sentiment.limit_down) == (None, None)
    assert sentiment.broken_rate is None
    assert sentiment.as_of == "2026-11-26"
