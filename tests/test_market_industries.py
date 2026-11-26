import re
import sys
from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from market.fetch import Industries, _parse_industries, fetch_industries


def _industry_frame(values=None):
    values = values if values is not None else [-5.5, -4.5, -3.5, -2.5, -1.5, -0.5,
                                              0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
    return pd.DataFrame({
        "板块": [f"行业{chr(65 + i)}" for i in range(len(values))],
        "涨跌幅": values,
    })


def test_parse_industries_splits_top_and_bottom_five():
    industries = _parse_industries(_industry_frame(), "2026-11-26 15:00")

    assert isinstance(industries, Industries)
    assert industries.gainers == [
        ("行业L", 5.5),
        ("行业K", 4.5),
        ("行业J", 3.5),
        ("行业I", 2.5),
        ("行业H", 1.5),
    ]
    assert industries.losers == [
        ("行业A", -5.5),
        ("行业B", -4.5),
        ("行业C", -3.5),
        ("行业D", -2.5),
        ("行业E", -1.5),
    ]
    assert industries.as_of == "2026-11-26 15:00"
    assert industries.source == "同花顺"


def test_parse_industries_drops_non_numeric_and_nan_rows():
    frame = _industry_frame([float("nan"), 9.0, None, "abc", -5.5, -4.5, -3.5, -2.5, -1.5,
                             0.5, 1.5, 2.5, 3.5, 4.5])
    frame.loc[len(frame)] = ["坏数据", "+8.0%"]

    industries = _parse_industries(frame, "2026-11-26 15:00")

    assert industries.gainers[0] == ("行业B", 9.0)
    assert all(name not in {"坏数据"} for name, _ in industries.gainers + industries.losers)
    assert len(industries.gainers) == 5
    assert len(industries.losers) == 5


def test_parse_industries_empty_frame_keeps_as_of():
    industries = _parse_industries(pd.DataFrame(), "2026-11-26 15:00")

    assert industries.gainers == []
    assert industries.losers == []
    assert industries.note == "行业榜无数据"
    assert industries.as_of == "2026-11-26 15:00"
    assert industries.source == "同花顺"


def test_parse_industries_fewer_than_five_takes_all():
    industries = _parse_industries(_industry_frame([3.0, 1.0]), "2026-11-26 15:00")

    assert industries.gainers == [("行业A", 3.0), ("行业B", 1.0)]
    assert industries.losers == [("行业B", 1.0), ("行业A", 3.0)]


def test_fetch_industries_historical_date_skips_akshare(monkeypatch):
    calls = []

    def summary():
        calls.append(True)
        return _industry_frame()

    monkeypatch.setitem(
        sys.modules, "akshare", SimpleNamespace(stock_board_industry_summary_ths=summary)
    )

    industries = fetch_industries("2020-01-02")

    assert calls == []
    assert industries.gainers == []
    assert industries.losers == []
    assert industries.as_of == "2020-01-02"
    assert industries.note == "仅当日，历史不可用"
    assert industries.source == "同花顺"


def test_fetch_industries_calls_akshare_and_parses(monkeypatch):
    calls = []

    def summary():
        calls.append(True)
        return _industry_frame()

    monkeypatch.setitem(
        sys.modules, "akshare", SimpleNamespace(stock_board_industry_summary_ths=summary)
    )

    industries = fetch_industries(datetime.now().strftime("%Y-%m-%d"))

    assert calls == [True]
    assert industries.gainers[0] == ("行业L", 5.5)
    assert industries.losers[0] == ("行业A", -5.5)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", industries.as_of)
