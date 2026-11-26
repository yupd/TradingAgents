from types import SimpleNamespace

import pandas as pd

from market.fetch import (
    _parse_limit_up,
    _parse_pool_count,
    fetch_broken_pool,
    fetch_limit_down_pool,
    fetch_limit_up,
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
