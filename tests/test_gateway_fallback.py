from tradingagents.llm_clients.openai_client import OpenAIClient


def test_openai_compatible_inherits_claude_code_gateway(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "gateway-token")
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)

    llm = OpenAIClient("deepseek-flash", provider="openai_compatible").get_llm()
    assert llm.openai_api_base == "https://gateway.example/v1"
    assert llm.openai_api_key.get_secret_value() == "gateway-token"


def test_dedicated_compatible_key_wins(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "gateway-token")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "dedicated-key")

    llm = OpenAIClient("deepseek-flash", provider="openai_compatible",
                       base_url="https://gateway.example/v1").get_llm()
    assert llm.openai_api_key.get_secret_value() == "dedicated-key"
