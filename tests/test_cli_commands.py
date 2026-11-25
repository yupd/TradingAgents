"""The CLI keeps running an analysis with no arguments, alongside its commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import cli.main as m


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr(m, "run_analysis", lambda **kw: calls.append(("analysis", kw)))
    calls.clear()
    return CliRunner()


calls: list = []


@pytest.mark.unit
def test_no_arguments_still_runs_an_analysis(runner):
    assert runner.invoke(m.app, []).exit_code == 0
    no_flags = {"ticker": None, "date": None, "analysts": None, "save": None, "show": None, "html": None}
    assert calls == [("analysis", {"checkpoint": None, "flags": no_flags})]


@pytest.mark.unit
def test_options_still_parse_without_a_subcommand(runner):
    assert runner.invoke(m.app, ["--checkpoint"]).exit_code == 0
    assert calls[0][1]["checkpoint"] is True


@pytest.mark.unit
def test_every_command_is_registered_when_run_as_a_module():
    """README documents `python -m cli.main`, which executes the file top to
    bottom, so a command defined after the __main__ block would not exist."""
    import os
    import subprocess
    import sys

    out = subprocess.run([sys.executable, "-m", "cli.main", "--help"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120)
    assert out.returncode == 0, out.stderr[-400:]
    assert "login" in out.stdout


@pytest.mark.unit
def test_login_and_logout_chatgpt_do_not_run_an_analysis(runner, monkeypatch):
    from tradingagents.llm_clients import chatgpt_auth

    monkeypatch.setattr(chatgpt_auth, "sign_in", lambda say: "a@example.com")
    monkeypatch.setattr(chatgpt_auth, "sign_out", lambda: "revoked")
    signed_in = runner.invoke(m.app, ["login", "chatgpt"])
    assert signed_in.exit_code == 0 and "Signed in to ChatGPT as a@example.com" in signed_in.output
    signed_out = runner.invoke(m.app, ["logout", "chatgpt"])
    assert signed_out.exit_code == 0 and "Signed out of ChatGPT" in signed_out.output
    assert runner.invoke(m.app, ["login", "claude"]).exit_code != 0
    assert calls == []


@pytest.mark.unit
def test_a_failed_login_exits_with_the_reason(runner, monkeypatch):
    from tradingagents.llm_clients import chatgpt_auth

    def refuse(say):
        raise chatgpt_auth.ChatGPTAuthError("Signing in with ChatGPT timed out")

    monkeypatch.setattr(chatgpt_auth, "sign_in", refuse)
    result = runner.invoke(m.app, ["login", "chatgpt"])
    assert result.exit_code == 1 and "timed out" in result.output


@pytest.mark.unit
@pytest.mark.parametrize("outcome, said", [
    (None, "Not signed in"), ("forgotten", "could not be reached to revoke"),
])
def test_logout_says_whether_openai_revoked_the_sign_in(runner, monkeypatch, outcome, said):
    from tradingagents.llm_clients import chatgpt_auth

    monkeypatch.setattr(chatgpt_auth, "sign_out", lambda: outcome)
    result = runner.invoke(m.app, ["logout", "chatgpt"])
    assert result.exit_code == 0 and said in " ".join(result.output.split())


@pytest.mark.unit
def test_a_failure_message_with_brackets_is_printed_as_text(runner, monkeypatch):
    from tradingagents.llm_clients import chatgpt_auth

    def refuse(say):
        raise chatgpt_auth.ChatGPTAuthError("ChatGPT sign-in failed ([/bogus]); sign in again.")

    monkeypatch.setattr(chatgpt_auth, "sign_in", refuse)
    result = runner.invoke(m.app, ["login", "chatgpt"])
    assert result.exit_code == 1 and "[/bogus]" in result.output
