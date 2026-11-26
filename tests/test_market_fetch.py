from types import SimpleNamespace

from market.fetch import IndexSpec, _tencent_index_bars


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
