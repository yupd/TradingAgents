import pandas as pd

from market.fundamentals import MacroItem, _latest_row, fetch_macro

SOURCE = "akshare 宏观接口（东方财富/国家统计局口径）"


def _install(monkeypatch, **overrides):
    import akshare as ak

    functions = {
        "macro_china_cpi": lambda: pd.DataFrame(
            {"月份": ["2026年09月", "2026年10月"], "全国-同比增长": [0.1, 0.3]}
        ),
        "macro_china_ppi": lambda: pd.DataFrame(
            {"月份": ["2026年10月"], "当月同比增长": [-2.1]}
        ),
        "macro_china_pmi": lambda: pd.DataFrame(
            {
                "月份": ["2026年10月"],
                "制造业-指数": [49.5],
                "非制造业-指数": [50.1],
            }
        ),
        "macro_china_consumer_goods_retail": lambda: pd.DataFrame(
            {"月份": ["2026年10月"], "同比增长": [2.9]}
        ),
        "macro_china_fixed_asset_investment": lambda: pd.DataFrame(
            {"月份": ["2025年10月", "2026年10月"], "自年初累计": [400000.0, 440000.0]}
        ),
        "macro_china_customs_trade": lambda: pd.DataFrame(
            {
                "月份": ["2026年10月"],
                "当月出口额-同比增长": [5.4],
                "当月进口额-同比增长": [1.2],
            }
        ),
    }
    functions.update(overrides)
    for name, fake in functions.items():
        monkeypatch.setattr(ak, name, fake)


def _item(items, name):
    return next(item for item in items if item.name == name)


def test_fetch_macro_returns_six_items_in_fixed_order(monkeypatch):
    _install(monkeypatch)

    block = fetch_macro()

    assert [item.name for item in block.items] == [
        "CPI",
        "PPI",
        "PMI",
        "社零",
        "固定资产投资",
        "进出口",
    ]
    assert isinstance(block.items[0], MacroItem)
    assert all(item.source == SOURCE for item in block.items)

    cpi = _item(block.items, "CPI")
    assert (cpi.value, cpi.unit, cpi.period) == (0.3, "%", "2026年10月")

    ppi = _item(block.items, "PPI")
    assert (ppi.value, ppi.unit, ppi.period) == (-2.1, "%", "2026年10月")

    pmi = _item(block.items, "PMI")
    assert (pmi.value, pmi.unit) == (49.5, "指数")
    assert "50.1" in pmi.note

    retail = _item(block.items, "社零")
    assert (retail.value, retail.unit) == (2.9, "%")

    fai = _item(block.items, "固定资产投资")
    assert round(fai.value, 4) == 10.0
    assert fai.unit == "%"
    assert fai.note == "自年初累计同比（按累计值计算）"

    trade = _item(block.items, "进出口")
    assert (trade.value, trade.unit) == (5.4, "%")
    assert "1.2" in trade.note


def test_latest_row_ignores_row_order_and_unparseable_months():
    frame = pd.DataFrame(
        {"月份": ["2026年09月", "not a month", "2026年10月", "2025年12月"]}
    )

    assert _latest_row(frame)["月份"] == "2026年10月"
    assert _latest_row(pd.DataFrame()) is None
    assert _latest_row(pd.DataFrame({"月份": ["unknown"]})) is None
    assert _latest_row(None) is None


def test_missing_column_degrades_value_but_keeps_period(monkeypatch):
    _install(
        monkeypatch,
        macro_china_cpi=lambda: pd.DataFrame({"月份": ["2026年10月"], "其他": [1.0]}),
    )

    cpi = _item(fetch_macro().items, "CPI")

    assert cpi.value is None
    assert cpi.period == "2026年10月"
    assert cpi.source == SOURCE


def test_empty_table_degrades_to_none_and_other_items_survive(monkeypatch):
    _install(monkeypatch, macro_china_ppi=lambda: pd.DataFrame())

    block = fetch_macro()
    ppi = _item(block.items, "PPI")

    assert (ppi.value, ppi.period) == (None, None)
    assert _item(block.items, "CPI").value == 0.3
    assert _item(block.items, "社零").value == 2.9


def test_fixed_asset_investment_missing_prior_year_month_is_none(monkeypatch):
    _install(
        monkeypatch,
        macro_china_fixed_asset_investment=lambda: pd.DataFrame(
            {"月份": ["2026年10月"], "自年初累计": [440000.0]}
        ),
    )

    fai = _item(fetch_macro().items, "固定资产投资")

    assert fai.value is None
    assert fai.note == "自年初累计同比（按累计值计算）"


def test_fixed_asset_investment_non_positive_prior_value_is_none(monkeypatch):
    _install(
        monkeypatch,
        macro_china_fixed_asset_investment=lambda: pd.DataFrame(
            {"月份": ["2025年10月", "2026年10月"], "自年初累计": [0.0, 440000.0]}
        ),
    )

    assert _item(fetch_macro().items, "固定资产投资").value is None


def test_trade_keeps_import_note_when_export_missing(monkeypatch):
    _install(
        monkeypatch,
        macro_china_customs_trade=lambda: pd.DataFrame(
            {"月份": ["2026年10月"], "当月进口额-同比增长": [1.2]}
        ),
    )

    trade = _item(fetch_macro().items, "进出口")

    assert trade.value is None
    assert "1.2" in trade.note


def test_single_failing_item_does_not_break_others(monkeypatch):
    def boom():
        raise RuntimeError("ppi down")

    _install(monkeypatch, macro_china_ppi=boom)

    block = fetch_macro()
    ppi = _item(block.items, "PPI")

    assert (ppi.value, ppi.period, ppi.unit) == (None, None, "%")
    assert [round(item.value, 4) for item in block.items if item.name != "PPI"] == [
        0.3,
        49.5,
        2.9,
        10.0,
        5.4,
    ]
