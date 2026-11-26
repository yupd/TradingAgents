from types import SimpleNamespace

import pandas as pd

from market.fetch import _parse_limit_up, fetch_limit_up


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
