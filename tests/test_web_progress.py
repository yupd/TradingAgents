from web.progress import PIPELINE_STAGES, STAGE_IDS, ProgressTracker


def test_stages_are_the_eleven_this_fork_has():
    assert STAGE_IDS == [
        "market", "social", "news", "fundamentals", "policy", "hot_money", "lockup",
        "debate", "trader", "risk", "pm",
    ]
    assert len(PIPELINE_STAGES) == 11


def test_pause_blocks_until_resume():
    t = ProgressTracker(ticker="600519", trade_date="2026-11-26")
    t.is_running = True
    assert t.pause() is True
    assert t.is_paused is True
    assert t.resume() is True
    assert t.is_paused is False


def test_stop_clears_progress_and_mark_complete_keeps_saved_path():
    t = ProgressTracker()
    t.mark_stage_done("market", "报告")
    t.saved_path = "/tmp/report"
    t.mark_complete({"final_trade_decision": "评级: 买入"}, "Buy")
    assert t.is_complete is True
    assert t.saved_path == "/tmp/report"
    assert t.stage_status("market") == "done"
