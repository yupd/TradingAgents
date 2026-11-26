import sys
import types

import pytest


class FakeSt:
    def __init__(self):
        self.session_state = {}
        self.inputs = {}
        self.errors = []

    def text_input(self, label, **kwargs):
        return self.inputs.get(kwargs.get("key", label), "")

    def selectbox(self, label, options, format_func=None, key=None, **kwargs):
        return list(options)[0]

    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture
def fake_st(monkeypatch):
    fake = FakeSt()
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    monkeypatch.setitem(sys.modules, "streamlit.components", types.ModuleType("streamlit.components"))
    return fake


def test_provider_list_starts_with_gateway_and_can_resolve_env_default(fake_st):
    from web.components import sidebar

    keys = sidebar._provider_keys()
    assert keys[0] == "openai_compatible"
    assert "chatgpt" not in keys and "bedrock" not in keys
    assert "deepseek" in keys


def test_custom_sentinel_requires_a_model_id(fake_st):
    from web.components import sidebar

    assert sidebar.validate_model_selection(
        {"quick_think_llm": "custom", "deep_think_llm": "deepseek-flash"}
    ) is not None
    assert sidebar.validate_model_selection(
        {"quick_think_llm": "", "deep_think_llm": "deepseek-flash"}
    ) is not None
    assert sidebar.validate_model_selection(
        {"quick_think_llm": "deepseek-flash", "deep_think_llm": "deepseek-flash"}
    ) is None


def test_user_input_accepts_only_ashare_codes(fake_st):
    from web.components import sidebar

    assert sidebar._resolve_user_input("SH600519") == ("600519", None)
    for raw in ("贵州茅台", "0700.HK", ""):
        code, err = sidebar._resolve_user_input(raw)
        assert code == "" and err
