"""Sidebar: stock input, LLM config, controls, and history list."""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path

import streamlit as st

from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS
from web.history import (
    clear_incomplete_task,
    get_history,
    get_incomplete_history,
    record_incomplete_task,
)

logger = logging.getLogger(__name__)

# Model selection survives browser tab close/reopen.
_LLM_CONFIG_PATH = Path(os.path.expanduser("~")) / ".tradingagents" / "llm_config.json"

# `MODEL_OPTIONS` uses this sentinel for "type the model ID yourself".
_CUSTOM_MODEL_SENTINEL = "custom"

_PROVIDER_LABELS = {
    "openai_compatible": "OpenAI 兼容（网关/自建）",
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google Gemini",
    "xai": "xAI Grok",
    "qwen": "通义千问 Qwen",
    "qwen-cn": "通义千问 Qwen（国内）",
    "glm": "智谱 GLM",
    "glm-cn": "智谱 GLM（国内）",
    "minimax": "MiniMax",
    "minimax-cn": "MiniMax（国内）",
    "openrouter": "OpenRouter",
    "ollama": "Ollama",
    "mistral": "Mistral",
    "kimi": "Kimi",
    "groq": "Groq",
    "nvidia": "NVIDIA",
}
_EXCLUDED_PROVIDERS = {"chatgpt", "bedrock"}


def _provider_keys() -> list[str]:
    """Providers the web picker offers, gateway first."""
    keys = [key for key in MODEL_OPTIONS if key not in _EXCLUDED_PROVIDERS]
    if "openai_compatible" in keys:
        keys.remove("openai_compatible")
        keys.insert(0, "openai_compatible")
    default = DEFAULT_CONFIG.get("llm_provider")
    if default and default not in keys:
        keys.append(default)
    return keys


def _resolve_model_value(value: str, text_key: str, label: str) -> str:
    """Turn a dropdown value into the model ID sent to the API."""
    if value != _CUSTOM_MODEL_SENTINEL:
        return value
    return st.text_input(
        label,
        key=text_key,
        placeholder="填该供应商实际支持的模型 ID，例: deepseek-v4-pro",
    ).strip()


def validate_model_selection(config: dict | None = None) -> str | None:
    """Block an empty or sentinel model ID before it becomes a server-side 400."""
    source = config if config is not None else st.session_state
    for label, key in (
        ("快速思考模型", "quick_think_llm"),
        ("深度思考模型", "deep_think_llm"),
    ):
        model = str(source.get(key) or "").strip()
        if not model or model == _CUSTOM_MODEL_SENTINEL:
            return (
                f"{label}的模型 ID 没填。请在「⚙️ 模型配置」里选一个模型，"
                "或选「Custom model ID」后填上该供应商实际支持的 ID。"
            )
    return None


def _load_saved_llm_config() -> None:
    """Restore the user's last model selection into session_state defaults."""
    try:
        cfg = json.loads(_LLM_CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}

    keys = _provider_keys()
    provider = cfg.get("llm_provider") or DEFAULT_CONFIG.get("llm_provider", "")
    st.session_state.setdefault(
        "llm_provider_idx", keys.index(provider) if provider in keys else 0
    )
    if "quick_model_idx" in cfg:
        st.session_state.setdefault("quick_model_idx", cfg["quick_model_idx"])
    if "deep_model_idx" in cfg:
        st.session_state.setdefault("deep_model_idx", cfg["deep_model_idx"])
    st.session_state.setdefault("llm_base_url", cfg.get("llm_base_url", ""))
    for key in ("custom_quick_model", "custom_deep_model"):
        if cfg.get(key):
            st.session_state.setdefault(key, cfg[key])

    # With no saved selection, start from .env's provider and model IDs.
    selected = keys[st.session_state["llm_provider_idx"]]
    if selected != DEFAULT_CONFIG.get("llm_provider"):
        return
    options = MODEL_OPTIONS.get(selected)
    if not options:
        return
    for mode, cfg_key, idx_key, text_key in (
        ("quick", "quick_think_llm", "quick_model_idx", "custom_quick_model"),
        ("deep", "deep_think_llm", "deep_model_idx", "custom_deep_model"),
    ):
        target = DEFAULT_CONFIG.get(cfg_key)
        values = [value for _, value in options[mode]]
        if not target:
            continue
        if target in values:
            st.session_state.setdefault(idx_key, values.index(target))
        else:
            st.session_state.setdefault(text_key, target)


def _save_llm_config() -> None:
    """Persist the current LLM config to disk (called before analysis)."""
    cfg = {
        "llm_provider": st.session_state.get("llm_provider", ""),
        "quick_model_idx": st.session_state.get("quick_model_idx", 0),
        "deep_model_idx": st.session_state.get("deep_model_idx", 0),
        "llm_base_url": st.session_state.get("llm_base_url", ""),
    }
    for key in ("custom_quick_model", "custom_deep_model"):
        val = st.session_state.get(key)
        if val:
            cfg[key] = val
    try:
        _LLM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LLM_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    except OSError as exc:
        logger.warning("LLM 配置持久化失败（不影响本次分析）: %s", exc)


def _resolve_user_input(raw: str) -> tuple[str, str | None]:
    """Resolve raw user input to (six-digit code, error message)."""
    try:
        return parse_ashare(raw).code, None
    except ValueError as exc:
        return "", str(exc)


def _render_analysis_controls(raw_ticker: str, trade_date_value: date) -> None:
    tracker = st.session_state.get("tracker")
    is_running = tracker is not None and tracker.is_running
    trade_date = trade_date_value.strftime("%Y-%m-%d")

    pause_col, resume_col, stop_col = st.columns(3)

    pause_disabled = not is_running or tracker.is_paused or tracker.stop_requested
    if pause_col.button(
        "暂停",
        key="sidebar_pause_analysis",
        use_container_width=True,
        disabled=pause_disabled,
    ):
        if tracker.pause():
            record_incomplete_task(
                tracker.ticker,
                tracker.trade_date,
                status="paused",
                completed_stages=tracker.completed_stages,
            )
        st.rerun()

    resume_disabled = not is_running or not tracker.is_paused or tracker.stop_requested
    if resume_col.button(
        "恢复",
        key="sidebar_resume_analysis",
        use_container_width=True,
        disabled=resume_disabled,
    ):
        if tracker.resume():
            record_incomplete_task(
                tracker.ticker,
                tracker.trade_date,
                status="running",
                completed_stages=tracker.completed_stages,
            )
        st.rerun()

    can_stop = tracker is not None or bool(raw_ticker.strip())
    if stop_col.button(
        "停止",
        key="sidebar_stop_analysis",
        use_container_width=True,
        disabled=not can_stop,
    ):
        target_ticker = tracker.ticker if tracker is not None and tracker.ticker else ""
        target_date = (
            tracker.trade_date
            if tracker is not None and tracker.trade_date
            else trade_date
        )

        if not target_ticker:
            target_ticker, err = _resolve_user_input(raw_ticker)
            if err:
                st.error(f"❌ {err}")
                return

        if tracker is not None and tracker.is_running:
            tracker.request_stop()
            clear_incomplete_task(target_ticker, target_date)
        else:
            if tracker is not None:
                tracker.mark_stopped()
                st.session_state["tracker"] = None
            # 断点数据库由下一次 fresh 运行在 runner 内清掉；这里只清任务索引。
            clear_incomplete_task(target_ticker, target_date)

        st.session_state["viewing_history"] = None
        st.success("已清空当前进度；下一次开始分析会从头生成。")
        st.rerun()

    if tracker is not None and tracker.stop_requested:
        st.caption("正在停止并清空，收尾完成后可重新开始。")


def _render_llm_config() -> None:
    """Render LLM provider and model selection controls."""
    keys = _provider_keys()
    provider_idx = st.selectbox(
        "LLM 供应商",
        range(len(keys)),
        format_func=lambda i: _PROVIDER_LABELS.get(keys[i], keys[i]),
        key="llm_provider_idx",
        help="选择你配置了 API Key 的供应商",
    )
    provider_key = keys[provider_idx]
    st.session_state["llm_provider"] = provider_key

    options = MODEL_OPTIONS.get(provider_key)
    if options:
        quick_options = options["quick"]
        deep_options = options["deep"]
        quick_labels = [label for label, _ in quick_options]
        quick_values = [value for _, value in quick_options]
        deep_labels = [label for label, _ in deep_options]
        deep_values = [value for _, value in deep_options]

        quick_idx = st.selectbox(
            "快速思考模型",
            range(len(quick_options)),
            format_func=lambda i: quick_labels[i],
            key="quick_model_idx",
            help="用于常规分析任务，速度优先",
        )
        st.session_state["quick_think_llm"] = _resolve_model_value(
            quick_values[quick_idx], "custom_quick_model", "快速思考模型 ID"
        )

        deep_idx = st.selectbox(
            "深度思考模型",
            range(len(deep_options)),
            format_func=lambda i: deep_labels[i],
            key="deep_model_idx",
            help="用于辩论/决策等需要深度推理的任务",
        )
        st.session_state["deep_think_llm"] = _resolve_model_value(
            deep_values[deep_idx], "custom_deep_model", "深度思考模型 ID"
        )
    else:
        st.session_state["quick_think_llm"] = st.text_input(
            "快速思考模型 ID", key="custom_quick_model"
        )
        st.session_state["deep_think_llm"] = st.text_input(
            "深度思考模型 ID", key="custom_deep_model"
        )

    base_url_required = provider_key == "openai_compatible"
    st.text_input(
        "API Base URL（第三方/代理" + ("·必填" if base_url_required else "，可选") + "）",
        key="llm_base_url",
        placeholder="例: https://your-relay.example/v1",
        help=(
            "通过第三方中转/代理访问模型时填写网关地址；留空则用所选供应商的官方地址。"
            "API Key 从 .env 读取，每个供应商用各自的环境变量——"
            "OpenAI=OPENAI_API_KEY、DeepSeek=DEEPSEEK_API_KEY、"
            "通义=DASHSCOPE_API_KEY、智谱=ZHIPU_API_KEY、MiniMax=MINIMAX_API_KEY、"
            "Claude=ANTHROPIC_API_KEY、OpenRouter=OPENROUTER_API_KEY、xAI=XAI_API_KEY、"
            "OpenAI 兼容（自定义）=OPENAI_COMPATIBLE_API_KEY。"
        ),
    )
    if base_url_required:
        st.caption(
            "已选「OpenAI 兼容（自定义）」：**Base URL 必填**（你的网关，走标准 Chat "
            "Completions），模型 ID 手动填写，Key 在 .env 设 `OPENAI_COMPATIBLE_API_KEY`。"
        )


def render_sidebar() -> None:
    """Render the sidebar with input controls and history."""
    _load_saved_llm_config()

    st.markdown(
        """
        <div style="text-align:center; margin-bottom:1.5rem;">
            <span style="font-size:2rem; font-weight:800; color:#ff5a1f;">Trading</span><span style="font-size:2rem; font-weight:800; color:#f5f1eb;">Agents</span>
            <div style="font-size:0.85rem; color:#888; margin-top:0.2rem;">
                A股多Agent投研系统
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("#### 新建分析")

    ticker = st.text_input(
        "股票代码",
        placeholder="例: 300750 或 SH600519",
        key="input_ticker",
        help="输入 6 位 A 股代码，支持 SH/SZ/BJ 前后缀",
    )

    trade_date = st.date_input(
        "分析日期",
        value=date.today(),
        key="input_date",
    )

    with st.expander("⚙️ 模型配置", expanded=False):
        _render_llm_config()

    tracker = st.session_state.get("tracker")
    is_busy = tracker is not None and tracker.is_running
    is_stopping = is_busy and tracker.stop_requested

    if st.button(
        "开始分析" if not is_busy else "停止中..." if is_stopping else "分析进行中...",
        use_container_width=True,
        disabled=is_busy or not ticker,
        type="primary",
    ):
        _save_llm_config()
        model_err = validate_model_selection()
        resolved_code, err = _resolve_user_input(ticker)
        if model_err:
            st.error(f"❌ {model_err}")
        elif err:
            st.error(f"❌ {err}")
        else:
            if resolved_code != ticker.strip():
                st.success(f"✅ {ticker.strip()} → {resolved_code}")
            st.session_state["start_analysis"] = {
                "ticker": resolved_code,
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "fresh": True,
            }
            st.session_state["viewing_history"] = None

    _render_analysis_controls(ticker, trade_date)

    st.markdown("---")
    st.markdown("#### 未完成任务")

    incomplete = get_incomplete_history()
    if not incomplete:
        st.caption("暂无未完成任务")
    else:
        for entry in incomplete[:10]:
            t, d = entry["ticker"], entry["trade_date"]
            status_label = {
                "error": "出错",
                "paused": "已暂停",
                "running": "进行中",
            }.get(entry.get("status"), "可继续")
            label = f"{t}  ·  {d}  ·  {status_label}"
            if st.button(
                label,
                key=f"resume_{t}_{d}",
                use_container_width=True,
                disabled=is_busy,
            ):
                st.session_state["start_analysis"] = {"ticker": t, "trade_date": d}
                st.session_state["viewing_history"] = None

    st.markdown("---")
    st.markdown("#### 历史记录")

    history = get_history()
    if not history:
        st.caption("暂无历史记录")
        return

    for entry in history[:20]:
        t, d = entry["ticker"], entry["date"]
        label = f"{t}  ·  {d}"
        if st.button(label, key=f"hist_{t}_{d}", use_container_width=True):
            st.session_state["viewing_history"] = entry["path"]
            st.session_state["start_analysis"] = None

    st.markdown("---")
    st.caption("⚠️ 仅供学习研究，不构成投资建议")
