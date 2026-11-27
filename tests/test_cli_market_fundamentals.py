"""The ``market --fundamentals`` switch and the assembly of one fundamentals report."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import cli.main as m
from market.fetch import Industries, IndexQuote, MarketNews, NewsResult, Sentiment, Turnover
from market.fundamentals import (
    Earnings,
    Fundamentals,
    MacroBlock,
    MacroItem,
    Margin,
    Valuation,
)
from market.summarize import Summary

DAY = "2026-11-26"
HISTORY = "2026-11-20"

HEADINGS = (
    "结论",
    "指数趋势",
    "两市成交额",
    "市场情绪",
    "行业强弱",
    "新闻与政策",
    "宏观基本面",
    "估值水平",
    "资金面",
    "盈利概览",
    "数据缺口",
)


def _fundamentals() -> Fundamentals:
    return Fundamentals(
        macro=MacroBlock(
            items=[MacroItem("CPI", 0.3, "%", "2026年10月", "akshare 宏观接口")]
        ),
        valuation=Valuation(
            pe_ttm=12.6,
            pe_percentile=45.2,
            percentile_window=120,
            pe_date="2026-11-01",
            official_pe1=13.61,
            source="乐咕乐股（akshare） / 中证指数（akshare）",
        ),
        margin=Margin(
            sh=100.0,
            sz=50.0,
            total=150.0,
            change_5d=10.0,
            as_of="2026-11-25",
            source="上交所/深交所（akshare）",
        ),
        earnings=Earnings(
            period="2026-09-30",
            net_profit_yoy=100.0,
            revenue_yoy=25.0,
            coverage=1.0,
            covered=10,
            total=10,
            source="东财业绩报表（akshare）",
        ),
    )


def _patch_market(monkeypatch, day=DAY, latest=DAY):
    """Trade day and latest session are configurable; the technical block is always present."""
    monkeypatch.setattr(
        "market.rules.resolve_trade_date",
        lambda requested: (latest, None) if requested is None else (day, None),
    )
    indices = [
        IndexQuote(name="沪深300", code="sh000300", close=100.0, source="tencent", as_of=day)
    ]
    monkeypatch.setattr("market.fetch.fetch_indices", lambda trade_date: indices)
    monkeypatch.setattr(
        "market.fetch.fetch_turnover",
        lambda trade_date: Turnover(sh=100.0, sz=200.0, total=300.0, as_of=day),
    )
    monkeypatch.setattr(
        "market.fetch.fetch_sentiment",
        lambda trade_date: Sentiment(limit_up=10, limit_down=1, broken=2, as_of=day),
    )
    monkeypatch.setattr(
        "market.fetch.fetch_industries",
        lambda trade_date: Industries(
            gainers=[("半导体", 3.0)], losers=[("银行", -1.0)], as_of=day
        ),
    )
    monkeypatch.setattr(
        "market.fetch.fetch_news",
        lambda trade_date: NewsResult(
            [MarketNews(title="标题", published_at=f"{day} 09:00", source="财联社")]
        ),
    )
    monkeypatch.setattr(
        "market.summarize.safe_summarize", lambda facts, llm: Summary("摘要")
    )
    monkeypatch.setattr(
        "tradingagents.llm_clients.create_tier_client",
        lambda config, tier: SimpleNamespace(get_llm=lambda: object()),
    )


def _patch_empty_market(monkeypatch, day=DAY):
    """Every technical source is empty, the case where the report must not be written."""
    monkeypatch.setattr("market.rules.resolve_trade_date", lambda requested: (day, None))
    monkeypatch.setattr(
        "market.fetch.fetch_indices",
        lambda trade_date: [IndexQuote(name="上证", code="sh000001")],
    )
    monkeypatch.setattr("market.fetch.fetch_turnover", lambda trade_date: Turnover())
    monkeypatch.setattr("market.fetch.fetch_sentiment", lambda trade_date: Sentiment())
    monkeypatch.setattr("market.fetch.fetch_industries", lambda trade_date: None)
    monkeypatch.setattr("market.fetch.fetch_news", lambda trade_date: NewsResult([]))


def _headings(text: str) -> list[str]:
    return [line.removeprefix("## ") for line in text.splitlines() if line.startswith("## ")]


@pytest.mark.unit
def test_market_help_shows_fundamentals_option():
    result = CliRunner().invoke(m.app, ["market", "--help"])

    assert result.exit_code == 0
    assert "--fundamentals" in result.output


@pytest.mark.unit
def test_market_command_passes_the_flag_through(monkeypatch):
    seen = []
    monkeypatch.setattr(
        m,
        "run_market",
        lambda date, fundamentals=False: seen.append(fundamentals) or Path("report.md"),
    )

    CliRunner().invoke(m.app, ["market", "--fundamentals"])
    CliRunner().invoke(m.app, ["market"])

    assert seen == [True, False]


@pytest.mark.unit
def test_enabled_latest_writes_four_sections_before_the_gaps(monkeypatch, tmp_path):
    _patch_market(monkeypatch)
    monkeypatch.setattr(
        "market.fundamentals.fetch_fundamentals", lambda day, is_latest: _fundamentals()
    )
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(m.app, ["market", "--fundamentals"])

    assert result.exit_code == 0
    text = (tmp_path / "reports" / "market" / f"{DAY}.md").read_text(encoding="utf-8")
    assert _headings(text) == list(HEADINGS)
    assert "第三方 PE(TTM)：12.60" in text
    assert "净利润同比：+100.00%" in text


@pytest.mark.unit
def test_historical_date_makes_no_fundamental_request(monkeypatch, tmp_path):
    _patch_market(monkeypatch, day=HISTORY, latest=DAY)
    calls = []

    def fake_fetch(*args, **kwargs):
        calls.append(args)
        return _fundamentals()

    monkeypatch.setattr("market.fundamentals.fetch_fundamentals", fake_fetch)
    monkeypatch.chdir(tmp_path)

    from cli.run import run_market

    path = run_market(HISTORY, fundamentals=True)

    assert calls == []
    text = path.read_text(encoding="utf-8")
    for heading in ("宏观基本面", "估值水平", "资金面", "盈利概览"):
        assert f"## {heading}\n\n历史模式不可用" in text
    assert "12.60" not in text


@pytest.mark.unit
def test_every_fundamentals_source_failing_still_exits_zero(monkeypatch, tmp_path):
    _patch_market(monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError("source down")

    for name in ("fetch_macro", "fetch_valuation", "fetch_margin", "fetch_earnings"):
        monkeypatch.setattr(f"market.fundamentals.{name}", boom)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(m.app, ["market", "--fundamentals"])

    assert result.exit_code == 0
    text = (tmp_path / "reports" / "market" / f"{DAY}.md").read_text(encoding="utf-8")
    for heading in ("宏观基本面", "估值水平", "资金面", "盈利概览"):
        assert f"## {heading}\n\n数据不可用" in text
    for gap in (
        "macro: 宏观数据不可用",
        "valuation: 估值数据不可用",
        "margin: 两融数据不可用",
        "earnings: 盈利数据不可用",
    ):
        assert f"- {gap}" in text


AKSHARE_LEAVES = (
    "macro_china_cpi",
    "macro_china_ppi",
    "macro_china_pmi",
    "macro_china_consumer_goods_retail",
    "macro_china_fixed_asset_investment",
    "macro_china_customs_trade",
    "stock_index_pe_lg",
    "index_value_csindex",
    "stock_margin_sse_js",
    "stock_margin_szse_js",
    "stock_yjbb_em",
)


@pytest.mark.unit
def test_every_akshare_leaf_failing_degrades_to_data_unavailable(monkeypatch, tmp_path):
    """Exercise the real fetch path: leaf failures must yield four 数据不可用 sections."""
    import akshare as ak

    _patch_market(monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError("source down")

    for name in AKSHARE_LEAVES:
        monkeypatch.setattr(ak, name, boom)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(m.app, ["market", "--fundamentals"])

    assert result.exit_code == 0
    text = (tmp_path / "reports" / "market" / f"{DAY}.md").read_text(encoding="utf-8")
    for heading in ("宏观基本面", "估值水平", "资金面", "盈利概览"):
        assert f"## {heading}\n\n数据不可用" in text
    for gap in (
        "macro: CPI 不可用",
        "macro: PPI 不可用",
        "macro: PMI 不可用",
        "macro: 社零 不可用",
        "macro: 固定资产投资 不可用",
        "macro: 进出口 不可用",
        "valuation: 第三方估值不可用",
        "valuation: 中证官方估值不可用",
        "margin: 两融数据不可用",
        "earnings: 盈利数据不可用",
    ):
        assert f"- {gap}" in text


@pytest.mark.unit
def test_fundamentals_with_bad_date_exits_2_without_writing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        m.app, ["market", "--fundamentals", "--date", "not-a-date"]
    )

    assert result.exit_code == 2
    assert not (tmp_path / "reports" / "market").exists()


@pytest.mark.unit
def test_all_technical_sources_empty_exits_1_even_with_fundamentals(monkeypatch, tmp_path):
    _patch_empty_market(monkeypatch)

    def fail(*args, **kwargs):
        raise AssertionError("fundamentals fetched before the empty gate")

    monkeypatch.setattr("market.fundamentals.fetch_fundamentals", fail)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(m.app, ["market", "--fundamentals"])

    assert result.exit_code == 1
    assert "没有可用的市场数据" in result.output
    assert not (tmp_path / "reports" / "market").exists()


@pytest.mark.unit
def test_default_run_never_calls_fundamentals(monkeypatch, tmp_path):
    _patch_market(monkeypatch)

    def fail(*args, **kwargs):
        raise AssertionError("fundamentals fetched without the flag")

    monkeypatch.setattr("market.fundamentals.fetch_fundamentals", fail)
    monkeypatch.chdir(tmp_path)

    from cli.run import run_market

    text = run_market(DAY).read_text(encoding="utf-8")

    assert _headings(text) == [*HEADINGS[:6], HEADINGS[-1]]
