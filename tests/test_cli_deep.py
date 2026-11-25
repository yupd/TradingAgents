from typer.testing import CliRunner

from cli.main import app


def test_deep_routes_market(monkeypatch):
    seen = {}
    monkeypatch.setattr("cli.main.run_deep", lambda code, **kw: seen.setdefault("code", code) or 0)
    result = CliRunner().invoke(app, ["deep", "600519", "2026-11-25"])
    assert result.exit_code == 0 and seen["code"] == "600519"


def test_cn_seven_hk_four_analysts(monkeypatch):
    seen = {}
    monkeypatch.setattr("cli.main.run_deep",
                        lambda code, **kw: seen.setdefault(code, kw.get("selected_analysts")) or 0)
    CliRunner().invoke(app, ["deep", "600519", "2026-11-25"])
    CliRunner().invoke(app, ["deep", "0700.HK", "2026-11-25"])
    assert len(seen["600519"]) == 7
    assert len(seen["0700.HK"]) == 4


def test_deep_rejects_unsupported(monkeypatch):
    result = CliRunner().invoke(app, ["deep", "AAPL"])
    assert result.exit_code == 2


def test_deep_accepts_resume(monkeypatch):
    seen = {}
    monkeypatch.setattr("cli.main.run_deep", lambda code, **kw: seen.setdefault("resume", kw.get("resume")) or 0)
    result = CliRunner().invoke(app, ["deep", "600519", "--resume"])
    assert result.exit_code == 0 and seen["resume"] is True
