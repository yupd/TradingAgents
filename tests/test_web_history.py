import json

from web import history


def test_incomplete_task_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_INCOMPLETE_TASKS_FILE", tmp_path / "incomplete.json")
    history.record_incomplete_task("600370", "2026-06-02", status="error",
                                   error="quota", completed_stages=["market"])
    entries = history.get_incomplete_history()
    assert entries[0]["ticker"] == "600370"
    assert entries[0]["status"] == "error"
    assert "checkpoint_step" not in entries[0]


def test_completed_history_hides_incomplete_task(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    log_dir = logs / "600370" / "TradingAgentsStrategy_logs"
    log_dir.mkdir(parents=True)
    (log_dir / "full_states_log_2026-06-02.json").write_text(
        json.dumps({"final_trade_decision": "评级: 买入"}), encoding="utf-8")
    monkeypatch.setattr(history, "_INCOMPLETE_TASKS_FILE", tmp_path / "incomplete.json")
    monkeypatch.setattr(history, "_results_dir", lambda: logs)
    history.record_incomplete_task("600370", "2026-06-02", status="running")
    assert history.get_incomplete_history() == []
    assert history.get_history()[0]["date"] == "2026-06-02"


def test_signal_prefers_saved_rating_then_decision_text():
    assert history.extract_signal({"final_rating": "Buy"}) == "Buy"
    assert history.extract_signal({"final_trade_decision": "评级：增持"}) == "Overweight"
    assert history.extract_signal({}) == "N/A"
