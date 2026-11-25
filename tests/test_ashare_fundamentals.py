import tradingagents.dataflows.vendors.a_share.fundamentals as f
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

ROWS = [
    {"period": "2026-09-30", "publish_date": "2026-10-28", "revenue": 100.0},
    {"period": "2026-06-30", "publish_date": "2026-08-20", "revenue": 90.0},
    {"period": "2025-09-30", "publish_date": None, "revenue": 80.0},
]


def test_historical_filters_by_publish_date(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: ROWS)
    rows = f.get_statement(parse_ashare("600519"), "income", "quarterly", "2026-09-15")
    assert [r.period for r in rows] == ["2026-06-30"]


def test_current_uses_latest(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: ROWS)
    rows = f.get_statement(parse_ashare("600519"), "income", "quarterly", None)
    assert rows[0].period == "2026-09-30"


def test_missing_publish_date_is_withheld_and_said(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: ROWS)
    text = f.get_income_statement("600519", "quarterly", "2026-09-15")
    assert "withheld: no publish date" in text
    assert "2025-09-30" not in text.split("withheld")[0]


def test_source_and_as_of_in_header(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: ROWS)
    text = f.get_income_statement("600519", "quarterly", "2026-09-15")
    assert "Source:" in text and "As of:" in text


def test_duplicate_period_keeps_the_latest_announcement(monkeypatch):
    rows = [
        {"period": "2026-06-30", "publish_date": "2026-08-31", "revenue": 95.0},
        {"period": "2026-06-30", "publish_date": "2026-08-20", "revenue": 90.0},
    ]
    monkeypatch.setattr(f, "_load_statement", lambda *a: rows)
    got = f.get_statement(parse_ashare("600519"), "income", "quarterly", "2026-09-15")
    assert len(got) == 1 and got[0].values["revenue"] == 95.0


def test_source_failure_returns_sentinel(monkeypatch):
    monkeypatch.setattr(f, "_load_statement", lambda *a: (_ for _ in ()).throw(RuntimeError("down")))
    text = f.get_income_statement("600519", "quarterly", "2026-09-15")
    assert text.startswith("DATA_UNAVAILABLE")


def test_statement_columns_exclude_metadata():
    rows = [{"period": "2026-09-30", "publish_date": "2026-10-28",
             "TOTAL_OPERATE_INCOME": 100.0, "INDUSTRY_CODE": 123.0, "REPORT_DATE": 1.0}]
    import tradingagents.dataflows.vendors.a_share.fundamentals as f
    from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare

    original = f._load_statement
    f._load_statement = lambda *a: rows
    try:
        text = f.get_income_statement("600519", "quarterly", None)
    finally:
        f._load_statement = original
    assert "TOTAL_OPERATE_INCOME" in text and "INDUSTRY_CODE" not in text
