import pytest
from pathlib import Path

from web import runner
from web.progress import ProgressTracker


class FakeGraph:
    def __init__(self, chunks, calls, stop_after=None, tracker=None):
        self.chunks, self.calls = chunks, calls
        self.stop_after, self.tracker = stop_after, tracker
        self.propagator = type("P", (), {"get_graph_args": staticmethod(lambda callbacks=None: {"config": {}})})()

    def clear_checkpoint_on_success(self, *a, **k): self.calls.append("clear")
    def begin_checkpoint(self, *a, **k): self.calls.append("begin"); return "tid"
    def create_run_state(self, *a, **k): return {}
    def checkpoint_input(self, init): return init
    def end_checkpoint(self): self.calls.append("end")
    def record_decision(self, *a, **k): self.calls.append("record")
    def save_reports(self, state, ticker): self.calls.append("save"); return Path("/tmp/x")

    def stream_run(self, inp, **args):
        for i, chunk in enumerate(self.chunks):
            if self.stop_after is not None and i == self.stop_after:
                self.tracker.stop_requested = True
            yield [], chunk


def _patched(monkeypatch, graph):
    calls = []
    monkeypatch.setattr(runner, "_new_graph", lambda config, stats: graph)
    monkeypatch.setattr(runner, "record_incomplete_task", lambda *a, **k: None)
    monkeypatch.setattr(runner, "clear_incomplete_task", lambda *a, **k: None)
    return calls


def test_all_stages_complete_and_report_is_saved(monkeypatch):
    tracker = ProgressTracker()
    chunks = [
        {"market_report": "m"}, {"sentiment_report": "s"}, {"news_report": "n"},
        {"fundamentals_report": "f"}, {"policy_report": "p"},
        {"hot_money_report": "h"}, {"lockup_report": "l"},
        {"investment_plan": "plan"}, {"trader_investment_plan": "trade"},
        {"final_trade_decision": "评级: 买入", "final_rating": "Buy"},
    ]
    graph = FakeGraph(chunks, [])
    _patched(monkeypatch, graph)
    runner._run("600519", "2026-11-26", {}, tracker)
    assert tracker.is_complete is True
    assert tracker.signal == "Buy"
    assert tracker.saved_path == "/tmp/x"
    assert all(tracker.stage_status(s) == "done" for s in
               ("market", "news", "fundamentals", "policy", "hot_money", "lockup",
                "debate", "trader", "risk", "pm"))


def test_fresh_clears_before_begin(monkeypatch):
    tracker = ProgressTracker()
    calls = []
    graph = FakeGraph([{"final_trade_decision": "买入", "final_rating": "Buy"}], calls)
    _patched(monkeypatch, graph)
    runner._run("600519", "2026-11-26", {}, tracker, fresh=True)
    assert calls[:2] == ["clear", "begin"]


def test_stop_clears_checkpoint_and_marks_stopped(monkeypatch):
    tracker = ProgressTracker()
    calls = []
    graph = FakeGraph([{"market_report": "m"}, {"news_report": "n"}], calls,
                      stop_after=1, tracker=tracker)
    _patched(monkeypatch, graph)
    runner._run("600519", "2026-11-26", {}, tracker)
    assert tracker.is_running is False
    assert tracker.is_complete is False
    assert tracker.error is None
    assert calls.count("clear") == 1
    assert "record" not in calls and "save" not in calls


def test_error_keeps_checkpoint(monkeypatch):
    tracker = ProgressTracker()
    calls = []

    class Boom(FakeGraph):
        def stream_run(self, inp, **args):
            raise RuntimeError("boom")

    graph = Boom([], calls)
    _patched(monkeypatch, graph)
    thread = runner.run_analysis_in_thread("600519", "2026-11-26", {}, tracker)
    thread.join(5)
    assert tracker.error == "boom"
    assert "clear" not in calls


def test_a_stage_already_marked_active_still_completes(monkeypatch):
    tracker = ProgressTracker()
    tracker.mark_stage_active("market")
    graph = FakeGraph([{"market_report": "m"}], [])
    _patched(monkeypatch, graph)
    runner._run("600519", "2026-11-26", {}, tracker)
    assert tracker.stage_status("market") == "done"


def test_incomplete_task_gets_a_snapshot_not_the_live_list(monkeypatch):
    tracker = ProgressTracker()
    tracker.mark_stage_active("market")
    captured = []
    graph = FakeGraph([{"market_report": "m"}], [])
    monkeypatch.setattr(runner, "_new_graph", lambda config, stats: graph)
    monkeypatch.setattr(runner, "clear_incomplete_task", lambda *a, **k: None)
    monkeypatch.setattr(
        runner,
        "record_incomplete_task",
        lambda *a, **k: captured.append(k.get("completed_stages")),
    )
    runner._run("600519", "2026-11-26", {}, tracker)
    assert captured
    assert all(stages is not tracker.completed_stages for stages in captured)


def test_end_checkpoint_runs_when_state_build_fails(monkeypatch):
    calls = []

    class CreateBoom(FakeGraph):
        def create_run_state(self, *a, **k):
            raise RuntimeError("state")

    graph = CreateBoom([], calls)
    _patched(monkeypatch, graph)
    with pytest.raises(RuntimeError):
        runner._run("600519", "2026-11-26", {}, ProgressTracker())
    assert "end" in calls


def test_save_failure_keeps_the_checkpoint(monkeypatch):
    tracker = ProgressTracker()
    calls = []

    class SaveBoom(FakeGraph):
        def save_reports(self, *a, **k):
            raise RuntimeError("disk")

    graph = SaveBoom([{"final_trade_decision": "评级: 买入", "final_rating": "Buy"}], calls)
    _patched(monkeypatch, graph)
    thread = runner.run_analysis_in_thread("600519", "2026-11-26", {}, tracker)
    thread.join(5)
    assert tracker.error == "disk"
    assert "clear" not in calls
