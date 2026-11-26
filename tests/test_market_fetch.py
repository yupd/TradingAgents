from datetime import datetime, timedelta
from types import SimpleNamespace

from market.fetch import (
    INDEXES,
    IndexSpec,
    _em_index_bars,
    _sina_index_bars,
    _tencent_index_bars,
    fetch_index_bars,
    fetch_indices,
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
    assert all(start < trade_date for _, start, _ in calls)


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
        assert (quote.name, quote.close, quote.return_60d) == (spec.name, None, None)
    healthy = [q for q in quotes if q.code not in {none_spec.code, error_spec.code}]
    assert all(quote.close is not None and quote.return_60d is not None for quote in healthy)
