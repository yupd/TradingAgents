"""The ``market`` command and the assembly of one market report."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import cli.main as m
from market.fetch import Industries, IndexQuote, MarketNews, NewsResult, Sentiment, Turnover
from market.summarize import Summary

HEADINGS = (
    "结论",
    "指数趋势",
    "两市成交额",
    "市场情绪",
    "行业强弱",
    "新闻与政策",
    "数据缺口",
)


@pytest.mark.unit
def test_market_help_shows_date_option():
    result = CliRunner().invoke(m.app, ["market", "--help"])
    assert result.exit_code == 0
    assert "--date" in result.output


@pytest.mark.unit
def test_market_command_prints_written_path(monkeypatch, tmp_path):
    target = tmp_path / "2026-11-26.md"
    monkeypatch.setattr(m, "run_market", lambda date: target)
    result = CliRunner().invoke(m.app, ["market", "--date", "2026-11-26"])
    assert result.exit_code == 0
    assert str(target) in result.output


@pytest.mark.unit
def test_market_command_rejects_bad_date(monkeypatch):
    def refuse(date):
        raise ValueError("time data 'x' does not match format '%Y-%m-%d'")

    monkeypatch.setattr(m, "run_market", refuse)
    result = CliRunner().invoke(m.app, ["market", "--date", "x"])
    assert result.exit_code != 0
    assert "does not match format" in result.output


@pytest.mark.unit
def test_run_market_writes_the_seven_sections(monkeypatch, tmp_path):
    day = "2026-11-26"
    indices = [
        IndexQuote(
            name="沪深300",
            code="sh000300",
            close=100.0,
            change_pct=1.0,
            return_5d=2.0,
            return_20d=5.0,
            return_60d=8.0,
            ma20=90.0,
            ma60=80.0,
            volume_ratio=1.3,
            source="tencent",
            as_of=day,
        )
    ]
    turnover = Turnover(sh=100.0, sz=200.0, total=300.0, as_of=day, source="上交所/深交所")
    sentiment = Sentiment(
        limit_up=10, limit_down=1, broken=2, broken_rate=16.7, as_of=day, source="东财"
    )
    industries = Industries(
        gainers=[("半导体", 3.0)], losers=[("银行", -1.0)], as_of=day, source="同花顺"
    )
    news = NewsResult(
        [MarketNews(title="标题", published_at="2026-11-26 09:00", source="财联社")]
    )

    monkeypatch.setattr("market.rules.resolve_trade_date", lambda date: (day, None))
    monkeypatch.setattr("market.fetch.fetch_indices", lambda trade_date: indices)
    monkeypatch.setattr("market.fetch.fetch_turnover", lambda trade_date: turnover)
    monkeypatch.setattr("market.fetch.fetch_sentiment", lambda trade_date: sentiment)
    monkeypatch.setattr("market.fetch.fetch_industries", lambda trade_date: industries)
    monkeypatch.setattr("market.fetch.fetch_news", lambda trade_date: news)
    monkeypatch.setattr("market.summarize.safe_summarize", lambda facts, llm: Summary("摘要"))
    monkeypatch.setattr(
        "tradingagents.llm_clients.create_tier_client",
        lambda config, tier: SimpleNamespace(get_llm=lambda: object()),
    )
    monkeypatch.chdir(tmp_path)

    from cli.run import run_market

    path = run_market(day)

    assert path == Path("reports/market") / f"{day}.md"
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert f"# A 股大盘复盘 {day}" in text
    for heading in HEADINGS:
        assert f"## {heading}" in text
