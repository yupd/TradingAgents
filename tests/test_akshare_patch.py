import requests

from tradingagents.dataflows.vendors.a_share import akshare_patch as p


def test_non_eastmoney_passes_through_untouched(monkeypatch):
    seen = {}

    def fake(url, **kwargs):
        seen.update(kwargs)
        return "ok"

    assert p._wrap(fake)("https://example.com/x") == "ok"
    assert "headers" not in seen


def test_eastmoney_gets_headers_and_retries(monkeypatch):
    calls = []
    monkeypatch.setattr(p.http.time, "sleep", lambda _s: None)

    def down(url, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("down")

    import pytest
    with pytest.raises(RuntimeError):
        p._wrap(down)("https://push2.eastmoney.com/api/qt/stock/get")
    assert len(calls) == 3
    assert calls[0]["headers"]["User-Agent"].startswith("Mozilla")


def test_install_is_idempotent_and_restores(monkeypatch):
    original = requests.get
    monkeypatch.setattr(p, "_installed", False)
    try:
        assert p.install() is True
        assert p.install() is False
    finally:
        requests.get = original
        p._installed = False
