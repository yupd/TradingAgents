import pandas as pd

from market.fundamentals import OFFICIAL_SOURCE, PE_SOURCE, Valuation, fetch_valuation

TRADE_DATE = "2026-11-27"


def _monthly(values, end="2026-11-01"):
    return pd.DataFrame(
        {
            "日期": pd.date_range(end=end, periods=len(values), freq="MS"),
            "滚动市盈率": values,
        }
    )


def _install(monkeypatch, history=None, official=None):
    import akshare as ak

    monkeypatch.setattr(
        ak, "stock_index_pe_lg", history or (lambda symbol: _monthly(list(range(1, 150))))
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
