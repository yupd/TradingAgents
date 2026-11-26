"""Background thread runner for the TradingAgents graph."""

from __future__ import annotations

import re
import threading
import traceback

from web.history import clear_incomplete_task, record_incomplete_task
from web.progress import ProgressTracker
from web.stock_display import normalize_report_state_mentions, normalize_stock_mentions

from tradingagents.agents.rating import run_rating


ANALYSTS = ("market", "social", "news", "fundamentals", "policy", "hot_money", "lockup")

_ANALYST_STAGES = (
    ("market", "market_report"),
    ("social", "sentiment_report"),
    ("news", "news_report"),
    ("fundamentals", "fundamentals_report"),
    ("policy", "policy_report"),
    ("hot_money", "hot_money_report"),
    ("lockup", "lockup_report"),
)


def _new_graph(config: dict, stats):
    """Build the graph; the single construction point tests replace."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph(ANALYSTS, config=config, debug=False, callbacks=[stats])


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from LLM output."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def _detect_completed_stages(merged: dict, tracker: ProgressTracker) -> None:
    """Mark stages whose output has landed in the merged run state."""
    for stage_id, report_key in _ANALYST_STAGES:
        content = merged.get(report_key)
        if content and tracker.stage_status(stage_id) != "done":
            report = normalize_stock_mentions(str(content), tracker.ticker, merged)
            tracker.mark_stage_done(stage_id, _strip_think_tags(report))

    if merged.get("investment_plan") and tracker.stage_status("debate") != "done":
        tracker.mark_stage_done(
            "debate",
            normalize_stock_mentions(str(merged["investment_plan"]), tracker.ticker, merged),
        )

    if merged.get("trader_investment_plan") and tracker.stage_status("trader") != "done":
        tracker.mark_stage_done(
            "trader",
            normalize_stock_mentions(str(merged["trader_investment_plan"]), tracker.ticker, merged),
        )

    # The portfolio manager runs after the risk discussion; its decision means both are over.
    if merged.get("final_trade_decision") and tracker.stage_status("risk") != "done":
        tracker.mark_stage_done("risk")
    if merged.get("final_trade_decision") and tracker.stage_status("pm") != "done":
        tracker.mark_stage_done(
            "pm",
            normalize_stock_mentions(str(merged["final_trade_decision"]), tracker.ticker, merged),
        )


def _infer_active_stage(tracker: ProgressTracker) -> None:
    """Set the current_stage to the first non-completed stage."""
    from web.progress import STAGE_IDS

    for sid in STAGE_IDS:
        if tracker.stage_status(sid) == "pending":
            tracker.mark_stage_active(sid)
            return


def _run(
    ticker: str,
    trade_date: str,
    config: dict,
    tracker: ProgressTracker,
    fresh: bool = False,
) -> None:
    """Execute the full pipeline in the current thread."""
    from cli.stats_handler import StatsCallbackHandler

    tracker.ticker = ticker
    tracker.trade_date = trade_date
    stats = StatsCallbackHandler()
    graph = _new_graph(config, stats)

    # A fresh run must not silently resume a checkpoint with the same signature.
    if fresh:
        graph.clear_checkpoint_on_success(ticker, trade_date)

    checkpoint_tid = graph.begin_checkpoint(ticker, trade_date)
    merged: dict = {}
    stream = None
    try:
        init_state = graph.create_run_state(ticker, trade_date)
        args = graph.propagator.get_graph_args(callbacks=[stats])
        if checkpoint_tid is not None:
            args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = checkpoint_tid

        stream = graph.stream_run(graph.checkpoint_input(init_state), **args)
        for _messages, chunk in stream:
            tracker.wait_if_paused()
            if tracker.stop_requested:
                break
            if chunk is not None:
                merged.update(chunk)
                _detect_completed_stages(merged, tracker)
                _infer_active_stage(tracker)

            record_incomplete_task(
                ticker,
                trade_date,
                status="paused" if tracker.is_paused else "running",
                completed_stages=list(tracker.completed_stages),
            )
            s = stats.get_stats()
            tracker.update_stats(s["llm_calls"], s["tool_calls"], s["tokens_in"], s["tokens_out"])
    finally:
        if stream is not None:
            stream.close()
        graph.end_checkpoint()

    if tracker.stop_requested:
        clear_incomplete_task(ticker, trade_date)
        graph.clear_checkpoint_on_success(ticker, trade_date)
        tracker.mark_stopped()
        return

    normalize_report_state_mentions(merged, ticker)
    graph.record_decision(ticker, trade_date, merged)
    saved = graph.save_reports(merged, ticker)
    # Only a fully written report may drop the checkpoint; a save failure keeps it resumable.
    graph.clear_checkpoint_on_success(ticker, trade_date)
    tracker.saved_path = str(saved)
    tracker.mark_complete(merged, run_rating(merged))
    clear_incomplete_task(ticker, trade_date)


def run_analysis_in_thread(
    ticker: str,
    trade_date: str,
    config: dict,
    tracker: ProgressTracker,
    fresh: bool = False,
) -> threading.Thread:
    """Launch the pipeline in a daemon thread. Returns the thread handle."""
    tracker.ticker = ticker
    tracker.trade_date = trade_date
    tracker.is_running = True
    tracker.mark_stage_active("market")
    record_incomplete_task(
        ticker,
        trade_date,
        status="running",
        completed_stages=list(tracker.completed_stages),
    )

    def _target() -> None:
        try:
            _run(ticker, trade_date, config, tracker, fresh=fresh)
        except Exception as exc:
            if tracker.stop_requested:
                return
            traceback.print_exc()
            record_incomplete_task(
                ticker,
                trade_date,
                status="error",
                error=str(exc),
                completed_stages=list(tracker.completed_stages),
            )
            tracker.mark_error(str(exc))

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t
