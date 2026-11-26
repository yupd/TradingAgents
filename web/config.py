"""Build a run config from the UI values, keeping empty model IDs visible to validation."""

from __future__ import annotations

from tradingagents.dataflows.vendors.a_share.market import apply_default_market_config
from tradingagents.default_config import DEFAULT_CONFIG


def build_run_config(values: dict, ticker: str) -> dict:
    config = DEFAULT_CONFIG.copy()

    if values.get("llm_provider"):
        config["llm_provider"] = values["llm_provider"]
    for key in ("deep_think_llm", "quick_think_llm"):
        if key in values:
            # An empty value must stay empty so the consumption point can reject it.
            config[key] = values[key]

    # .env's gateway belongs to .env's provider; another provider uses its own endpoint.
    default_backend = (
        DEFAULT_CONFIG.get("backend_url")
        if config["llm_provider"] == DEFAULT_CONFIG.get("llm_provider")
        else None
    )
    backend_url = (values.get("llm_base_url") or default_backend or "").strip()
    config["backend_url"] = backend_url or None
    config["checkpoint_enabled"] = True
    config["output_language"] = "Chinese"
    return apply_default_market_config(ticker, config)
