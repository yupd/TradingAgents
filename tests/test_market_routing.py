from tradingagents.dataflows.vendors.a_share.market import apply_market_config
from tradingagents.default_config import DEFAULT_CONFIG


def test_cn_uses_ashare():
    cfg = apply_market_config("600519", DEFAULT_CONFIG)
    assert cfg["data_vendors"]["core_stock_apis"] == "a_share"
    assert cfg["data_vendors"]["fundamental_data"].startswith("a_share")


def test_hk_uses_yfinance():
    cfg = apply_market_config("0700.HK", DEFAULT_CONFIG)
    assert cfg["data_vendors"]["core_stock_apis"] == "yfinance"
