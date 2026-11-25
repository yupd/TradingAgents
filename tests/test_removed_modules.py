import importlib.util


def test_removed_modules_are_gone():
    for name in ("tradingagents.memory", "tradingagents.backtest", "tradingagents.portfolio"):
        assert importlib.util.find_spec(name) is None, f"{name} should be removed"
