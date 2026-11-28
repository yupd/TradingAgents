import pandas as pd
import pytest
import requests

import market.fundamentals as fundamentals
from market.fundamentals import (
    BFW_SOURCE,
    DJ_SOURCE,
    INDEX_SPECS,
    OFFICIAL_SOURCE,
    PE_SOURCE,
    IndexValuation,
    Valuation,
    _danjuan_index,
    fetch_valuation,
)

TRADE_DATE = "2026-11-27"


def test_index_specs_order_and_mapping():
    assert [
        (spec.name, spec.code, spec.baifenwei_slug) for spec in INDEX_SPECS
    ] == [
        ("沪深300", "SH000300", "hs300"),
        ("创业板", "SZ399006", "cyb"),
        ("科创50", "SH000688", "kc50"),
        ("中证500", "SH000905", "zz500"),
        ("中证1000", "SH000852", "zz1000"),
    ]
    assert DJ_SOURCE == "蛋卷基金（第三方）"
    assert BFW_SOURCE == "百分位.com（第三方）"


def test_valuation_indexes_default_to_isolated_empty_lists():
    first, second = Valuation(), Valuation()
    assert first.indexes == []
    assert first.indexes is not second.indexes


def _monthly(values, end="2026-11-01"):
    return pd.DataFrame(
        {
            "日期": pd.date_range(end=end, periods=len(values), freq="MS"),
            "滚动市盈率": values,
        }
    )


def _install(monkeypatch, history=None, official=None, indexes=None):
    import akshare as ak

    monkeypatch.setattr(
        ak, "stock_index_pe_lg", history or (lambda symbol: _monthly(list(range(1, 150))))
    )
    monkeypatch.setattr(
        fundamentals,
        "_danjuan_index",
        indexes or (lambda spec, trade_date: None),
    )
    if official is None:
        official = lambda symbol: pd.DataFrame(
            {
                "日期": pd.to_datetime(["2026-11-25", "2026-11-26", "2026-12-01"]),
                "市盈率1": [13.10, 13.61, 99.0],
                "市盈率2": [14.10, 14.69, 99.0],
                "股息率1": [2.50, 2.60, 9.0],
                "股息率2": [2.40, 2.50, 9.0],
            }
        )
    monkeypatch.setattr(ak, "index_value_csindex", official)


def test_percentile_uses_last_120_months(monkeypatch):
    _install(monkeypatch)

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.pe_ttm == 149.0
    assert valuation.pe_date == "2026-11-01"
    assert valuation.percentile_window == 120
    assert valuation.pe_percentile == 100.0
    assert valuation.source == f"{PE_SOURCE} / {OFFICIAL_SOURCE}"


def test_rows_after_trade_date_are_ignored(monkeypatch):
    frame = _monthly(list(range(1, 121)) + [9999.0], end="2026-12-01")
    _install(monkeypatch, history=lambda symbol: frame)

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.pe_ttm == 120.0
    assert valuation.pe_date == "2026-11-01"
    assert valuation.pe_percentile == 100.0


def test_median_series_gives_about_half_percentile(monkeypatch):
    values = list(range(1, 120)) + [59.5]  # 119 values plus the latest at the median
    _install(monkeypatch, history=lambda symbol: _monthly(values))

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.pe_percentile == 50.0
    assert valuation.percentile_window == 120


def test_short_history_uses_actual_window(monkeypatch):
    values = list(range(1, 36)) + [17.5]
    _install(monkeypatch, history=lambda symbol: _monthly(values))

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.percentile_window == 36
    assert valuation.pe_percentile == 50.0


def test_official_valuation_keeps_latest_row_at_or_before_trade_date(monkeypatch):
    _install(monkeypatch)

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.official_pe1 == 13.61
    assert valuation.official_pe2 == 14.69
    assert valuation.official_div1 == 2.60
    assert valuation.official_div2 == 2.50
    assert valuation.official_date == "2026-11-26"


def test_official_source_failure_keeps_third_party(monkeypatch):
    def boom(symbol):
        raise RuntimeError("csindex down")

    _install(monkeypatch, official=boom)

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.pe_ttm == 149.0
    assert valuation.pe_percentile == 100.0
    assert valuation.official_pe1 is None
    assert valuation.official_pe2 is None
    assert valuation.official_div1 is None
    assert valuation.official_div2 is None
    assert valuation.official_date is None
    assert valuation.source == PE_SOURCE


def test_third_party_failure_keeps_official(monkeypatch):
    def boom(symbol):
        raise RuntimeError("legulegu down")

    _install(monkeypatch, history=boom)

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.pe_ttm is None
    assert valuation.pe_percentile is None
    assert valuation.percentile_window is None
    assert valuation.official_pe1 == 13.61
    assert valuation.source == OFFICIAL_SOURCE


def test_both_sources_fail_returns_empty_valuation(monkeypatch):
    def boom(symbol):
        raise RuntimeError("down")

    _install(monkeypatch, history=boom, official=boom)

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation == Valuation()
    assert valuation.source is None


# Real 2026-11-27 payload raw values: (pe, pb, pe_percentile, pb_percentile).
DJ_PAYLOADS = {
    "SH000300": (13.643, 1.3554, 0.7012, 0.2552),
    "SZ399006": (27.4511, 3.8626, 0.0624, 0.1716),
    "SH000688": (99.81, 6.7208, 0.766, 0.7481),
    "SH000905": (26.9565, 1.9738, 0.5688, 0.5364),
    "SH000852": (35.7077, 1.876, 0.3328, 0.0828),
}
# Expected record after percent conversion: (pe, pe%, pb, pb%).
DJ_EXPECTED = {
    "SH000300": (13.643, 70.1, 1.3554, 25.5),
    "SZ399006": (27.4511, 6.2, 3.8626, 17.2),
    "SH000688": (99.81, 76.6, 6.7208, 74.8),
    "SH000905": (26.9565, 56.9, 1.9738, 53.6),
    "SH000852": (35.7077, 33.3, 1.876, 8.3),
}
DJ_TS = 1795708800000  # 2026-11-27 00:00 Beijing


def _dj_payload(code, ts=DJ_TS, result_code=0):
    pe, pb, pe_pct, pb_pct = DJ_PAYLOADS[code]
    return {
        "result_code": result_code,
        "data": {
            "pe": pe,
            "pb": pb,
            "pe_percentile": pe_pct,
            "pb_percentile": pb_pct,
            "ts": ts,
            "date": "11-27",
        },
    }


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_danjuan_detail_maps_all_five_indexes(monkeypatch):
    def fake_get(url, **kwargs):
        return _Response(_dj_payload(url.rsplit("/", 1)[-1]))

    monkeypatch.setattr(fundamentals.requests, "get", fake_get)

    records = [_danjuan_index(spec, TRADE_DATE) for spec in INDEX_SPECS]

    assert records == [
        IndexValuation(
            name=spec.name,
            code=spec.code,
            pe=DJ_EXPECTED[spec.code][0],
            pe_percentile=DJ_EXPECTED[spec.code][1],
            pb=DJ_EXPECTED[spec.code][2],
            pb_percentile=DJ_EXPECTED[spec.code][3],
            as_of="2026-11-27",
            source=DJ_SOURCE,
        )
        for spec in INDEX_SPECS
    ]
    assert [record.code for record in records] == [spec.code for spec in INDEX_SPECS]


def test_danjuan_hits_each_code_once_with_timeout_four(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(_dj_payload(url.rsplit("/", 1)[-1]))

    monkeypatch.setattr(fundamentals.requests, "get", fake_get)

    for spec in INDEX_SPECS:
        _danjuan_index(spec, TRADE_DATE)

    assert [url for url, _ in calls] == [
        f"https://danjuanfunds.com/djapi/index_eva/detail/{spec.code}"
        for spec in INDEX_SPECS
    ]
    assert all(kwargs["timeout"] == 4 for _, kwargs in calls)
    assert len(calls) == len(INDEX_SPECS)  # exactly one attempt per index


def test_danjuan_future_ts_is_rejected(monkeypatch):
    monkeypatch.setattr(
        fundamentals.requests,
        "get",
        lambda url, **kwargs: _Response(_dj_payload("SH000300", ts=1795795200000)),
    )

    assert _danjuan_index(INDEX_SPECS[0], TRADE_DATE) is None


DJ_BASE_DATA = {
    "pe": DJ_PAYLOADS["SH000300"][0],
    "pb": DJ_PAYLOADS["SH000300"][1],
    "pe_percentile": DJ_PAYLOADS["SH000300"][2],
    "pb_percentile": DJ_PAYLOADS["SH000300"][3],
    "ts": DJ_TS,
    "date": "11-27",
}


def _without(key):
    data = dict(DJ_BASE_DATA)
    data.pop(key)
    return data


def _with(**overrides):
    data = dict(DJ_BASE_DATA)
    data.update(overrides)
    return data


DJ_BAD_PAYLOADS = {
    "result_code_nonzero": {"result_code": 1, "data": DJ_BASE_DATA},
    "result_code_login_error": {"result_code": 300001, "data": DJ_BASE_DATA},
    "data_missing": {"result_code": 0},
    "data_not_dict": {"result_code": 0, "data": [1, 2]},
    "pe_missing": {"result_code": 0, "data": _without("pe")},
    "pe_non_numeric": {"result_code": 0, "data": _with(pe="abc")},
    "pe_none": {"result_code": 0, "data": _with(pe=None)},
    "pe_zero": {"result_code": 0, "data": _with(pe=0)},
    "pe_negative": {"result_code": 0, "data": _with(pe=-1.0)},
    "pb_missing": {"result_code": 0, "data": _without("pb")},
    "pb_non_numeric": {"result_code": 0, "data": _with(pb="abc")},
    "pb_none": {"result_code": 0, "data": _with(pb=None)},
    "pb_zero": {"result_code": 0, "data": _with(pb=0)},
    "pb_negative": {"result_code": 0, "data": _with(pb=-1.0)},
    "pe_percentile_missing": {"result_code": 0, "data": _without("pe_percentile")},
    "pe_percentile_non_numeric": {
        "result_code": 0,
        "data": _with(pe_percentile="abc"),
    },
    "pe_percentile_negative": {"result_code": 0, "data": _with(pe_percentile=-0.1)},
    "pe_percentile_above_one": {"result_code": 0, "data": _with(pe_percentile=1.1)},
    "pb_percentile_missing": {"result_code": 0, "data": _without("pb_percentile")},
    "pb_percentile_non_numeric": {
        "result_code": 0,
        "data": _with(pb_percentile="abc"),
    },
    "pb_percentile_negative": {"result_code": 0, "data": _with(pb_percentile=-0.1)},
    "pb_percentile_above_one": {"result_code": 0, "data": _with(pb_percentile=1.1)},
    "ts_missing": {"result_code": 0, "data": _without("ts")},
    "ts_non_numeric": {"result_code": 0, "data": _with(ts="soon")},
    "ts_future": {"result_code": 0, "data": _with(ts=1795795200000)},
}


@pytest.mark.parametrize(
    "payload", DJ_BAD_PAYLOADS.values(), ids=DJ_BAD_PAYLOADS.keys()
)
def test_danjuan_malformed_payloads_return_none(monkeypatch, payload):
    monkeypatch.setattr(
        fundamentals.requests, "get", lambda url, **kwargs: _Response(payload)
    )

    assert _danjuan_index(INDEX_SPECS[0], TRADE_DATE) is None


@pytest.mark.parametrize(
    "error", [requests.Timeout("timeout"), requests.ConnectionError("down")]
)
def test_danjuan_transport_errors_return_none(monkeypatch, error):
    def fake_get(url, **kwargs):
        raise error

    monkeypatch.setattr(fundamentals.requests, "get", fake_get)

    assert _danjuan_index(INDEX_SPECS[0], TRADE_DATE) is None


class _BadJSONResponse:
    def json(self):
        raise ValueError("not json")


def test_danjuan_non_json_body_returns_none(monkeypatch):
    monkeypatch.setattr(
        fundamentals.requests, "get", lambda url, **kwargs: _BadJSONResponse()
    )

    assert _danjuan_index(INDEX_SPECS[0], TRADE_DATE) is None


@pytest.mark.parametrize("trade_date", [None, 20261127])
def test_danjuan_bad_trade_date_type_returns_none(monkeypatch, trade_date):
    monkeypatch.setattr(
        fundamentals.requests,
        "get",
        lambda url, **kwargs: _Response({"result_code": 0, "data": DJ_BASE_DATA}),
    )

    assert _danjuan_index(INDEX_SPECS[0], trade_date) is None


def test_danjuan_string_zero_result_code_is_accepted(monkeypatch):
    monkeypatch.setattr(
        fundamentals.requests,
        "get",
        lambda url, **kwargs: _Response({"result_code": "0", "data": DJ_BASE_DATA}),
    )

    record = _danjuan_index(INDEX_SPECS[0], TRADE_DATE)

    assert record is not None
    assert record.code == "SH000300"


def _records():
    return [
        IndexValuation(
            name=spec.name,
            code=spec.code,
            pe=DJ_EXPECTED[spec.code][0],
            pe_percentile=DJ_EXPECTED[spec.code][1],
            pb=DJ_EXPECTED[spec.code][2],
            pb_percentile=DJ_EXPECTED[spec.code][3],
            as_of="2026-11-27",
            source=DJ_SOURCE,
        )
        for spec in INDEX_SPECS
    ]


def test_fetch_valuation_collects_five_indexes_in_spec_order(monkeypatch):
    records = _records()
    by_code = {record.code: record for record in records}
    _install(monkeypatch, indexes=lambda spec, trade_date: by_code[spec.code])

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.indexes == records
    assert [record.code for record in valuation.indexes] == [
        spec.code for spec in INDEX_SPECS
    ]


def test_fetch_valuation_skips_a_missing_index(monkeypatch):
    records = _records()
    by_code = {record.code: record for record in records}
    missing = INDEX_SPECS[2].code

    def fake(spec, trade_date):
        return None if spec.code == missing else by_code[spec.code]

    _install(monkeypatch, indexes=fake)

    valuation = fetch_valuation(TRADE_DATE)

    assert len(valuation.indexes) == 4
    assert missing not in [record.code for record in valuation.indexes]


def test_fetch_valuation_all_indexes_missing_keeps_empty_valuation(monkeypatch):
    def boom(symbol):
        raise RuntimeError("down")

    _install(monkeypatch, history=boom, official=boom)

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.indexes == []
    assert valuation == Valuation()


def test_fetch_valuation_isolates_one_index_exception(monkeypatch):
    records = _records()
    by_code = {record.code: record for record in records}
    broken = INDEX_SPECS[1].code

    def fake(spec, trade_date):
        if spec.code == broken:
            raise RuntimeError("danjuan down")
        return by_code[spec.code]

    _install(monkeypatch, indexes=fake)

    valuation = fetch_valuation(TRADE_DATE)

    assert [record.code for record in valuation.indexes] == [
        spec.code for spec in INDEX_SPECS if spec.code != broken
    ]


def test_index_records_leave_hs300_fields_unchanged(monkeypatch):
    by_code = {record.code: record for record in _records()}
    _install(monkeypatch, indexes=lambda spec, trade_date: by_code[spec.code])

    valuation = fetch_valuation(TRADE_DATE)

    assert valuation.pe_ttm == 149.0
    assert valuation.pe_percentile == 100.0
    assert valuation.official_pe1 == 13.61
    assert valuation.source == f"{PE_SOURCE} / {OFFICIAL_SOURCE}"
