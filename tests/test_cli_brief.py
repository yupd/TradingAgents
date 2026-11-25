from typer.testing import CliRunner

from cli.main import app


def test_brief_command_runs(monkeypatch, tmp_path):
    monkeypatch.setattr("cli.main.run_brief", lambda **kw: tmp_path / "brief.md")
    result = CliRunner().invoke(app, ["brief", "--date", "2026-11-25", "--watchlist", "w.yaml"])
    assert result.exit_code == 0
