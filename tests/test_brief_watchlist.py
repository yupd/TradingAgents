import pytest

from brief.watchlist import load_watchlist


def test_load_and_dedupe(tmp_path):
    p = tmp_path / "w.yaml"
    p.write_text("stocks:\n  - code: 600519\n    notes: 白酒\n  - code: 600519\n  - code: 000001\n", encoding="utf-8")
    items = load_watchlist(p)
    assert [i.code for i in items] == ["600519", "000001"]
    assert items[0].notes == "白酒"


def test_invalid_code_raises(tmp_path):
    p = tmp_path / "w.yaml"
    p.write_text("stocks:\n  - code: 0700.HK\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_watchlist(p)
