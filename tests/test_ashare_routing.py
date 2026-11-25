from tradingagents.dataflows import router
from tradingagents.dataflows.config import set_config


def test_ashare_registered_for_core_methods():
    for method in ("get_stock_data", "get_fundamentals", "get_news",
                   "get_dragon_tiger_board", "get_lockup_expiry"):
        assert "a_share" in router.VENDOR_METHODS[method]


def test_configured_ashare_chain():
    set_config({"data_vendors": {"core_stock_apis": "a_share", "news_data": "a_share"}})
    assert router.get_vendor("core_stock_apis") == "a_share"
    assert router.get_vendor("news_data") == "a_share"
