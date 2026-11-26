from tradingagents.default_config import DEFAULT_CONFIG
from web.config import build_run_config


def test_empty_ui_model_is_not_replaced_by_the_default():
    config = build_run_config(
        {"llm_provider": "openai_compatible", "quick_think_llm": "",
         "deep_think_llm": "deepseek-flash"},
        "600519",
    )
    assert config["quick_think_llm"] == ""


def test_missing_ui_values_fall_back_to_defaults():
    config = build_run_config({}, "600519")
    assert config["quick_think_llm"] == DEFAULT_CONFIG["quick_think_llm"]
    assert config["deep_think_llm"] == DEFAULT_CONFIG["deep_think_llm"]
    assert config["checkpoint_enabled"] is True
    assert config["data_vendors"]["core_stock_apis"] == "a_share"


def test_switching_provider_does_not_reuse_the_default_gateway(monkeypatch):
    monkeypatch.setitem(DEFAULT_CONFIG, "llm_provider", "openai_compatible")
    monkeypatch.setitem(DEFAULT_CONFIG, "backend_url", "https://gw.example/v1")

    switched = build_run_config({"llm_provider": "deepseek"}, "600519")
    assert switched["backend_url"] is None

    same = build_run_config({"llm_provider": "openai_compatible"}, "600519")
    assert same["backend_url"] == "https://gw.example/v1"
