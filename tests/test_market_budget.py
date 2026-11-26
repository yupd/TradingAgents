"""The normal market run stays within the 12-source-call budget."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from market.fetch import Industries, MarketNews, NewsResult, Turnover
from market.summarize import Summary
from tradingagents.dataflows.vendors.a_share.types import DailyBar

DAY = "2026-11-26"


def _bars(count: int = 65) -> list[DailyBar]:
    """Synthetic daily bars long enough for every metric ``build_index_quote`` computes."""
    start = date(2026, 8, 1)
    return [
        DailyBar(
            date=(start + timedelta(days=i)).isoformat(),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.0 + i,
            volume=1000.0 + i,
            source="tencent",
            as_of=(start + timedelta(days=i)).isoformat(),
        )
        for i in range(count)
    ]


@pytest.mark.unit
def test_normal_market_run_uses_exactly_twelve_source_calls(monkeypatch, tmp_path):
    calls: list[str] = []

    def counted(name, result):
        def fake(*args, **kwargs):
            calls.append(name)
            return result

        return fake

    monkeypatch.setattr("market.rules.resolve_trade_date", lambda requested: (DAY, None))
    monkeypatch.setattr("market.fetch.fetch_index_bars", counted("fetch_index_bars", _bars()))
    monkeypatch.setattr(
        "market.fetch.fetch_sse_turnover",
        counted("fetch_sse_turnover", Turnover(sh=8000.0, source="上交所", as_of=DAY)),
    )
    monkeypatch.setattr(
        "market.fetch.fetch_szse_turnover",
        counted("fetch_szse_turnover", Turnover(sz=10000.0, source="深交所", as_of=DAY)),
    )
    monkeypatch.setattr("market.fetch.fetch_limit_up", counted("fetch_limit_up", (40, 3)))
    monkeypatch.setattr("market.fetch.fetch_broken_pool", counted("fetch_broken_pool", 5))
    monkeypatch.setattr(
        "market.fetch.fetch_limit_down_pool", counted("fetch_limit_down_pool", 2)
    )
    monkeypatch.setattr(
        "market.fetch.fetch_industries",
        counted(
            "fetch_industries",
            Industries(
                gainers=[("半导体", 3.0)], losers=[("银行", -1.0)], as_of=DAY, source="同花顺"
            ),
        ),
    )
    monkeypatch.setattr(
        "market.fetch.fetch_news",
        counted(
            "fetch_news",
            NewsResult(
                [MarketNews(title="标题", published_at="2026-11-26 09:00", source="财联社")]
            ),
        ),
    )
    monkeypatch.setattr("market.summarize.safe_summarize", lambda facts, llm: Summary("摘要"))
    monkeypatch.setattr(
        "tradingagents.llm_clients.create_tier_client",
        lambda config, tier: SimpleNamespace(get_llm=lambda: object()),
    )
    monkeypatch.chdir(tmp_path)

    from cli.run import run_market

    path = run_market(DAY)

    assert path.exists()
    assert calls.count("fetch_index_bars") == 5
    assert len(calls) == 12
    assert len(calls) <= 12
