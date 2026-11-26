import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from market.fetch import (
    INDEXES,
    IndexSpec,
    Turnover,
    _em_index_bars,
    _parse_sse_turnover,
    _parse_szse_turnover,
    _sina_index_bars,
    _tencent_index_bars,
    build_turnover,
    fetch_index_bars,
    fetch_indices,
    fetch_sse_turnover,
    fetch_szse_turnover,
    fetch_turnover,
)
from tradingagents.dataflows.vendors.a_share.types import DailyBar


def test_tencent_index_bars_maps_fields_and_filters_dates(monkeypatch):
    payload = {
        "data": {
            "sh000001": {
                "qfqday": [
                    ["2026-11-20", "3000", "3010", "3020", "2990", "123456"],
                    ["2026-11-24", "3010", "3030", "3040", "3000", "200000"],
                    ["2026-11-25", "3030", "3020", "3050", "3010", "210000"],
                    ["2026-11-26", "3020", "3080", "3090", "3015", "220000"],
                ]
            }
        }
    }
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append((url, params))
        return SimpleNamespace(json=lambda: payload)

    monkeypatch.setattr("market.fetch.http.em_get", fake_get)
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")

    bars = _tencent_index_bars(spec, "2026-11-24", "2026-11-26")

    assert len(bars) == 3
    assert calls == [
        (
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            {"param": "sh000001,day,2026-11-24,2026-11-26,640,qfq"},
        )
    ]
    first = bars[0]
    assert (
        first.date,
        first.open,
        first.high,
        first.low,
        first.close,
        first.volume,
    ) == ("2026-11-24", 3010.0, 3040.0, 3000.0, 3030.0, 200000.0)
    assert all(bar.source == "tencent" and bar.as_of == bar.date for bar in bars)


def test_tencent_index_bars_returns_empty_without_rows(monkeypatch):
    monkeypatch.setattr(
        "market.fetch.http.em_get", lambda *args, **kwargs: SimpleNamespace(json=lambda: {})
    )
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")

    assert _tencent_index_bars(spec, "2026-11-24", "2026-11-26") == []


def test_sina_index_bars_parses_jsonp_and_filters_dates(monkeypatch):
    text = (
        "["
        '{"day":"2026-11-20","open":"2990","high":"3020","low":"2980","close":"3010",'
        '"volume":"100"},'
        '{"day":"2026-11-25","open":"3010","high":"3040","low":"3000","close":"3030",'
        '"volume":"200"},'
        '{"day":"2026-11-26","open":"3030","high":"3090","low":"3015","close":"3080",'
        '"volume":"300"}'
        "]"
    )
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append((url, params))
        return SimpleNamespace(text=f"x({text})")

    monkeypatch.setattr("market.fetch.http.em_get", fake_get)
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")

    bars = _sina_index_bars(spec, "2026-11-25", "2026-11-26")

    assert calls == [
        (
            "https://quotes.sina.cn/cn/api/jsonp_v2.php/x/CN_MarketDataService.getKLineData",
            {"symbol": "sh000001", "scale": 240, "ma": "no", "datalen": 1023},
        )
    ]
    assert [
        (bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume) for bar in bars
    ] == [
        ("2026-11-25", 3010.0, 3040.0, 3000.0, 3030.0, 200.0),
        ("2026-11-26", 3030.0, 3090.0, 3015.0, 3080.0, 300.0),
    ]
    assert all(bar.source == "sina" and bar.as_of == bar.date for bar in bars)


def test_sina_index_bars_returns_empty_without_rows(monkeypatch):
    monkeypatch.setattr(
        "market.fetch.http.em_get", lambda *args, **kwargs: SimpleNamespace(text="x([])")
    )
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")

    assert _sina_index_bars(spec, "2026-11-24", "2026-11-26") == []


def test_em_index_bars_maps_fields_and_filters_dates(monkeypatch):
    payload = {
        "data": {
            "klines": [
                "2026-11-20,2990,3010,3020,2980,100",
                "2026-11-25,3010,3030,3040,3000,200",
                "2026-11-26,3030,3080,3090,3015,300",
            ]
        }
    }
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append((url, params))
        return SimpleNamespace(json=lambda: payload)

    monkeypatch.setattr("market.fetch.http.em_get", fake_get)
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")

    bars = _em_index_bars(spec, "2026-11-25", "2026-11-26")

    assert calls == [
        (
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            {
                "secid": "1.000001",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56",
                "klt": 101,
                "fqt": 1,
                "beg": "20261125",
                "end": "20261126",
            },
        )
    ]
    assert [
        (bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume) for bar in bars
    ] == [
        ("2026-11-25", 3010.0, 3040.0, 3000.0, 3030.0, 200.0),
        ("2026-11-26", 3030.0, 3090.0, 3015.0, 3080.0, 300.0),
    ]
    assert all(bar.source == "eastmoney" and bar.as_of == bar.date for bar in bars)


def test_em_index_bars_returns_empty_without_rows(monkeypatch):
    monkeypatch.setattr(
        "market.fetch.http.em_get", lambda *args, **kwargs: SimpleNamespace(json=lambda: {})
    )
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")

    assert _em_index_bars(spec, "2026-11-24", "2026-11-26") == []


def _make_bars(source: str, dates: list[str]) -> list[DailyBar]:
    return [
        DailyBar(date=day, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0,
                 source=source, as_of=day)
        for day in dates
    ]


def test_fetch_index_bars_falls_back_to_sina_on_tencent_error(monkeypatch):
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")
    expected = _make_bars("sina", ["2026-11-25", "2026-11-26"])
    calls = []

    def tencent(*args):
        calls.append("tencent")
        raise RuntimeError("tencent down")

    def sina(*args):
        calls.append("sina")
        return expected

    def eastmoney(*args):
        calls.append("eastmoney")
        raise AssertionError("eastmoney should not be reached")

    monkeypatch.setattr("market.fetch._tencent_index_bars", tencent)
    monkeypatch.setattr("market.fetch._sina_index_bars", sina)
    monkeypatch.setattr("market.fetch._em_index_bars", eastmoney)
    monkeypatch.setattr(
        "market.fetch.http.em_get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network used")),
    )

    bars = fetch_index_bars(spec, "2026-11-25", "2026-11-26")

    assert bars is expected
    assert [bar.source for bar in bars] == ["sina", "sina"]
    assert calls == ["tencent", "sina"]


def test_fetch_index_bars_falls_back_to_eastmoney_after_empty_and_error(monkeypatch):
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")
    expected = _make_bars("eastmoney", ["2026-11-26"])
    calls = []

    def tencent(*args):
        calls.append("tencent")
        return []

    def sina(*args):
        calls.append("sina")
        raise RuntimeError("sina down")

    def eastmoney(*args):
        calls.append("eastmoney")
        return expected

    monkeypatch.setattr("market.fetch._tencent_index_bars", tencent)
    monkeypatch.setattr("market.fetch._sina_index_bars", sina)
    monkeypatch.setattr("market.fetch._em_index_bars", eastmoney)
    monkeypatch.setattr(
        "market.fetch.http.em_get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network used")),
    )

    bars = fetch_index_bars(spec, "2026-11-25", "2026-11-26")

    assert [bar.source for bar in bars] == ["eastmoney"]
    assert calls == ["tencent", "sina", "eastmoney"]


def test_fetch_index_bars_returns_none_when_all_sources_fail(monkeypatch):
    spec = IndexSpec(name="上证", code="sh000001", exchange="SH")
    calls = []

    def fail(name):
        def inner(*args):
            calls.append(name)
            raise RuntimeError(f"{name} down")

        return inner

    monkeypatch.setattr("market.fetch._tencent_index_bars", fail("tencent"))
    monkeypatch.setattr("market.fetch._sina_index_bars", fail("sina"))
    monkeypatch.setattr("market.fetch._em_index_bars", fail("eastmoney"))
    monkeypatch.setattr(
        "market.fetch.http.em_get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network used")),
    )

    assert fetch_index_bars(spec, "2026-11-25", "2026-11-26") is None
    assert calls == ["tencent", "sina", "eastmoney"]


def _recent_days(end: str, count: int) -> list[str]:
    end_day = datetime.strptime(end, "%Y-%m-%d")
    return [(end_day - timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in range(count - 1, -1, -1)]


def _no_network(*args, **kwargs):
    raise AssertionError("network used")


def test_fetch_indices_returns_five_quotes_in_order(monkeypatch):
    trade_date = "2026-11-26"
    days = _recent_days(trade_date, 65)
    expected_start = (
        datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=400)
    ).strftime("%Y-%m-%d")
    calls = []

    def fake_fetch(spec, start, end):
        calls.append((spec, start, end))
        return _make_bars("fake", days)

    monkeypatch.setattr("market.fetch.fetch_index_bars", fake_fetch)
    monkeypatch.setattr("market.fetch.http.em_get", _no_network)

    quotes = fetch_indices(trade_date)

    assert [quote.name for quote in quotes] == [spec.name for spec in INDEXES]
    assert [quote.code for quote in quotes] == [spec.code for spec in INDEXES]
    assert all(quote.close == 1.0 for quote in quotes)
    assert all(quote.return_60d is not None and quote.ma60 is not None for quote in quotes)
    assert [spec for spec, _, _ in calls] == list(INDEXES)
    assert all(end == trade_date for _, _, end in calls)
    assert all(start == expected_start for _, start, _ in calls)


def test_fetch_indices_survives_none_and_exception(monkeypatch):
    trade_date = "2026-11-26"
    days = _recent_days(trade_date, 65)
    none_spec, error_spec = INDEXES[1], INDEXES[3]

    def fake_fetch(spec, start, end):
        if spec is none_spec:
            return None
        if spec is error_spec:
            raise RuntimeError("source down")
        return _make_bars("fake", days)

    monkeypatch.setattr("market.fetch.fetch_index_bars", fake_fetch)
    monkeypatch.setattr("market.fetch.http.em_get", _no_network)

    quotes = fetch_indices(trade_date)

    assert len(quotes) == 5
    assert [quote.code for quote in quotes] == [spec.code for spec in INDEXES]
    quotes_by_code = {quote.code: quote for quote in quotes}
    for spec in (none_spec, error_spec):
        quote = quotes_by_code[spec.code]
        assert (quote.name, quote.code) == (spec.name, spec.code)
        assert (
            quote.close,
            quote.change_pct,
            quote.return_5d,
            quote.return_20d,
            quote.return_60d,
            quote.ma20,
            quote.ma60,
            quote.volume_ratio,
            quote.source,
            quote.as_of,
        ) == (None,) * 10
    healthy = [q for q in quotes if q.code not in {none_spec.code, error_spec.code}]
    assert all(quote.close is not None and quote.return_60d is not None for quote in healthy)


def _sse_turnover_frame():
    import pandas as pd

    return pd.DataFrame({
        "单日情况": ["挂牌数", "市价总值", "流通市值", "成交金额", "成交量", "平均市盈率"],
        "股票": [2360, 607121.03, 550416.63, 6539.10, 473.97, 15.32],
    })


def test_parse_sse_turnover_reads_stock_turnover():
    turnover = _parse_sse_turnover(_sse_turnover_frame(), "2026-11-26")

    assert (turnover.sh, turnover.note, turnover.as_of) == (
        6539.10, "上交所-股票（含B股）", "2026-11-26",
    )


def test_parse_sse_turnover_returns_none_without_usable_value():
    import pandas as pd

    missing = pd.DataFrame({"单日情况": ["挂牌数", "成交量"], "股票": [2360, 473.97]})
    placeholder = pd.DataFrame({"单日情况": ["成交金额"], "股票": ["-"]})

    assert _parse_sse_turnover(missing, "2026-11-26") is None
    assert _parse_sse_turnover(placeholder, "2026-11-26") is None


def test_fetch_sse_turnover_passes_yyyymmdd_and_parses(monkeypatch):
    import sys
    from types import SimpleNamespace

    calls = []

    def fake(date):
        calls.append(date)
        return _sse_turnover_frame()

    # Fake module exposing only the old name exercises the getattr fallback.
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_sse_deal_daily=fake))

    turnover = fetch_sse_turnover("2026-11-26")

    assert calls == ["20261126"]
    assert (turnover.sh, turnover.as_of) == (6539.10, "2026-11-26")
    assert turnover.source == "上交所"


def test_fetch_sse_turnover_prefers_current_akshare_name(monkeypatch):
    import akshare as ak

    calls = []

    def fake(date):
        calls.append(date)
        return _sse_turnover_frame()

    monkeypatch.setattr(ak, "stock_deal_daily_sse", fake)

    assert fetch_sse_turnover("2026-11-26").sh == 6539.10
    assert calls == ["20261126"]


def _szse_turnover_frame(turnover=7.314446e11):
    import pandas as pd

    return pd.DataFrame({
        "证券类别": ["股票", "主板A股", "创业板A股"],
        "数量": [2879, 1500, 1379],
        "成交金额": [turnover, 3.0e11, 4.0e11],
        "总市值": [3.0e13, 2.0e13, 1.0e13],
        "流通市值": [2.5e13, 1.5e13, 1.0e13],
    })


def test_parse_szse_turnover_converts_yuan_to_yi():
    turnover = _parse_szse_turnover(_szse_turnover_frame(), "2026-11-26")

    assert turnover.sz == pytest.approx(7314.446)
    assert (turnover.note, turnover.as_of, turnover.source) == (
        "深交所-股票（含B股与创业板）", "2026-11-26", "深交所",
    )


def test_parse_szse_turnover_returns_none_without_usable_value():
    import pandas as pd

    missing = pd.DataFrame({"证券类别": ["主板A股"], "成交金额": [3.0e11]})
    placeholder = pd.DataFrame({"证券类别": ["股票"], "成交金额": ["-"]})
    nan_value = pd.DataFrame({"证券类别": ["股票"], "成交金额": [float("nan")]})

    assert _parse_szse_turnover(missing, "2026-11-26") is None
    assert _parse_szse_turnover(placeholder, "2026-11-26") is None
    assert _parse_szse_turnover(nan_value, "2026-11-26") is None


def test_fetch_szse_turnover_passes_yyyymmdd_and_parses(monkeypatch):
    import sys

    calls = []

    def fake(date):
        calls.append(date)
        return _szse_turnover_frame()

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_summary_szse=fake))

    turnover = fetch_szse_turnover("2026-11-26")

    assert calls == ["20261126"]
    assert (turnover.sz, turnover.as_of, turnover.source) == (
        pytest.approx(7314.446), "2026-11-26", "深交所",
    )


def test_fetch_szse_turnover_falls_back_to_old_name(monkeypatch):
    import sys

    calls = []

    def fake(date):
        calls.append(date)
        return _szse_turnover_frame()

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_szse_summary=fake))

    assert fetch_szse_turnover("2026-11-26").sz == pytest.approx(7314.446)
    assert calls == ["20261126"]


def test_build_turnover_sums_both_markets():
    turnover = build_turnover(
        Turnover(sh=6539.10), Turnover(sz=7314.446), "2026-11-26"
    )

    assert turnover.sh == pytest.approx(6539.10)
    assert turnover.sz == pytest.approx(7314.446)
    assert turnover.total == pytest.approx(13853.546)
    assert turnover.note == "沪深股票成交额（含B股）；量能倍数见指数小节（指数成交量口径）"
    assert turnover.as_of == "2026-11-26"
    assert turnover.source == "上交所/深交所"
    assert turnover.avg20 is None
    assert turnover.ratio is None


def test_build_turnover_leaves_total_none_when_one_side_missing():
    only_sz = build_turnover(None, Turnover(sz=7314.446), "2026-11-26")
    only_sh = build_turnover(Turnover(sh=6539.10), None, "2026-11-26")

    assert (only_sz.sh, only_sz.sz, only_sz.total) == (
        None, pytest.approx(7314.446), None,
    )
    assert (only_sh.sh, only_sh.sz, only_sh.total) == (
        pytest.approx(6539.10), None, None,
    )


def test_fetch_turnover_combines_both_sources_for_same_date(monkeypatch):
    calls = []

    def fake_sh(date):
        calls.append(("sh", date))
        return Turnover(sh=6539.10)

    def fake_sz(date):
        calls.append(("sz", date))
        return Turnover(sz=7314.446)

    monkeypatch.setattr("market.fetch.fetch_sse_turnover", fake_sh)
    monkeypatch.setattr("market.fetch.fetch_szse_turnover", fake_sz)

    turnover = fetch_turnover("2026-11-26")

    assert calls == [("sh", "2026-11-26"), ("sz", "2026-11-26")]
    assert turnover.total == pytest.approx(13853.546)
    assert (turnover.sh, turnover.sz) == (
        pytest.approx(6539.10), pytest.approx(7314.446),
    )


def test_fetch_turnover_keeps_sse_when_szse_raises(monkeypatch, caplog):
    def fake_sh(date):
        return Turnover(sh=6539.10)

    def fake_sz(date):
        raise RuntimeError("szse down")

    monkeypatch.setattr("market.fetch.fetch_sse_turnover", fake_sh)
    monkeypatch.setattr("market.fetch.fetch_szse_turnover", fake_sz)

    with caplog.at_level(logging.DEBUG, logger="market.fetch"):
        turnover = fetch_turnover("2026-11-26")

    degraded = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(degraded) == 1
    assert "SZSE" in degraded[0].getMessage()
    assert "szse down" in degraded[0].getMessage()
    assert turnover.sh == pytest.approx(6539.10)
    assert turnover.sz is None
    assert turnover.total is None
    assert turnover.note == "沪深股票成交额（含B股）；量能倍数见指数小节（指数成交量口径）"
    assert turnover.as_of == "2026-11-26"


def test_fetch_turnover_keeps_szse_when_sse_raises(monkeypatch):
    def fake_sh(date):
        raise RuntimeError("sse down")

    def fake_sz(date):
        return Turnover(sz=7314.446)

    monkeypatch.setattr("market.fetch.fetch_sse_turnover", fake_sh)
    monkeypatch.setattr("market.fetch.fetch_szse_turnover", fake_sz)

    turnover = fetch_turnover("2026-11-26")

    assert turnover.sh is None
    assert turnover.sz == pytest.approx(7314.446)
    assert turnover.total is None
    assert turnover.note == "沪深股票成交额（含B股）；量能倍数见指数小节（指数成交量口径）"
    assert turnover.as_of == "2026-11-26"


def test_fetch_turnover_returns_all_none_when_both_raise(monkeypatch):
    def fail(date):
        raise RuntimeError("source down")

    monkeypatch.setattr("market.fetch.fetch_sse_turnover", fail)
    monkeypatch.setattr("market.fetch.fetch_szse_turnover", fail)

    turnover = fetch_turnover("2026-11-26")

    assert (turnover.sh, turnover.sz, turnover.total) == (None, None, None)
    assert turnover.note == "沪深股票成交额（含B股）；量能倍数见指数小节（指数成交量口径）"
    assert turnover.as_of == "2026-11-26"
