import pytest

from tradingagents.dataflows.vendors.a_share.market import market_of
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare


@pytest.mark.parametrize("raw", ["600519", "SH600519", "600519.SH", "600519.SS", "sh600519"])
def test_shanghai_variants(raw):
    s = parse_ashare(raw)
    assert (s.code, s.exchange, s.yahoo, s.display) == ("600519", "SH", "600519.SS", "600519.SH")


@pytest.mark.parametrize(
    "raw,exchange",
    [("000001", "SZ"), ("SZ000001", "SZ"), ("300750", "SZ"),
     ("688017", "SH"), ("830799", "BJ"), ("430047", "BJ")],
)
def test_exchange_inference(raw, exchange):
    assert parse_ashare(raw).exchange == exchange


@pytest.mark.parametrize("raw", ["0700.HK", "AAPL", "", "60051", "6005190"])
def test_rejects_non_ashare(raw):
    with pytest.raises(ValueError):
        parse_ashare(raw)


def test_market_routing():
    assert market_of("600519") == "CN"
    assert market_of("600519.SH") == "CN"
    assert market_of("0700.HK") == "HK"
    with pytest.raises(ValueError):
        market_of("AAPL")
