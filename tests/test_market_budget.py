"""The default market run stays within 12 source calls; fundamentals adds ≤39, ≤44 with fallback."""

from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from market.fetch import Industries, MarketNews, NewsResult, Turnover
from market.fundamentals import DJ_SOURCE, IndexValuation
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


def _install_technical(monkeypatch, calls):
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
    return calls


def _install_llm(monkeypatch, tmp_path):
    monkeypatch.setattr("market.summarize.safe_summarize", lambda facts, llm: Summary("摘要"))
    monkeypatch.setattr(
        "tradingagents.llm_clients.create_tier_client",
        lambda config, tier: SimpleNamespace(get_llm=lambda: object()),
    )
    monkeypatch.chdir(tmp_path)


def _install_fundamentals(monkeypatch, calls, primary_ok=True):
    """Fake each akshare leaf; earnings fakes 12 pages per call like the real table."""
    import akshare as ak

    def index_record(spec):
        return IndexValuation(
            name=spec.name,
            code=spec.code,
            pe=12.6,
            pe_percentile=35.0,
            pb=1.4,
            pb_percentile=28.0,
            as_of=DAY,
            source=DJ_SOURCE,
        )

    def danjuan_index(spec, trade_date):
        calls.append("index_valuation")
        return index_record(spec) if primary_ok else None

    def baifenwei_index(spec, trade_date):
        calls.append("index_fallback")
        return None if primary_ok else index_record(spec)

    monkeypatch.setattr("market.fundamentals._danjuan_index", danjuan_index)
    monkeypatch.setattr("market.fundamentals._baifenwei_index", baifenwei_index)

    def counted(name, frame):
        def fake(*args, **kwargs):
            calls.append(name)
            return frame

        return fake

    macro_frames = (
        ("macro_china_cpi", {"月份": ["2026年10月"], "全国-同比增长": [0.3]}),
        ("macro_china_ppi", {"月份": ["2026年10月"], "当月同比增长": [-2.1]}),
        (
            "macro_china_pmi",
            {"月份": ["2026年10月"], "制造业-指数": [49.5], "非制造业-指数": [50.1]},
        ),
        ("macro_china_consumer_goods_retail", {"月份": ["2026年10月"], "同比增长": [4.8]}),
        (
            "macro_china_fixed_asset_investment",
            {"月份": ["2026年10月"], "自年初累计": [400000.0]},
        ),
        (
            "macro_china_customs_trade",
            {
                "月份": ["2026年10月"],
                "当月出口额-同比增长": [5.0],
                "当月进口额-同比增长": [3.0],
            },
        ),
    )
    for name, data in macro_frames:
        monkeypatch.setattr(ak, name, counted(name, pd.DataFrame(data)))

    monkeypatch.setattr(
        ak,
        "stock_index_pe_lg",
        counted(
            "valuation",
            pd.DataFrame({"日期": pd.to_datetime([DAY]), "滚动市盈率": [12.6]}),
        ),
    )
    monkeypatch.setattr(
        ak,
        "index_value_csindex",
        counted(
            "valuation",
            pd.DataFrame(
                {
                    "日期": pd.to_datetime([DAY]),
                    "市盈率1": [12.6],
                    "市盈率2": [13.0],
                    "股息率1": [2.5],
                    "股息率2": [2.4],
                }
            ),
        ),
    )

    margin_frame = pd.DataFrame({"日期": pd.to_datetime([DAY]), "融资融券余额": [1.5e12]})
    for name in ("stock_margin_sse_js", "stock_margin_szse_js"):
        monkeypatch.setattr(ak, name, counted("margin", margin_frame))

    def yjbb(date):
        calls.extend(["earnings"] * 12)  # akshare paginates the table ~12 times
        return pd.DataFrame(
            {
                "最新公告日期": pd.to_datetime([DAY]),
                "净利润-净利润": [100.0],
                "净利润-同比增长": [10.0],
                "营业总收入-营业总收入": [200.0],
                "营业总收入-同比增长": [5.0],
            }
        )

    monkeypatch.setattr(ak, "stock_yjbb_em", yjbb)
    return calls


@pytest.mark.unit
def test_normal_market_run_uses_exactly_twelve_source_calls(monkeypatch, tmp_path):
    calls: list[str] = []
    _install_technical(monkeypatch, calls)
    _install_llm(monkeypatch, tmp_path)

    from cli.run import run_market

    path = run_market(DAY)

    assert path.exists()
    assert calls.count("fetch_index_bars") == 5
    assert len(calls) == 12
    assert len(calls) <= 12


@pytest.mark.unit
def test_fundamentals_mode_uses_thirty_nine_source_calls_without_fallback(
    monkeypatch, tmp_path
):
    technical: list[str] = []
    fundamental: list[str] = []
    _install_technical(monkeypatch, technical)
    _install_fundamentals(monkeypatch, fundamental)
    _install_llm(monkeypatch, tmp_path)

    from cli.run import run_market

    path = run_market(DAY, fundamentals=True)

    assert path.exists()
    macro = [name for name in fundamental if name.startswith("macro_")]
    assert len(macro) == 6
    assert len(set(macro)) == 6  # each macro series exactly once
    assert fundamental.count("valuation") == 2
    assert fundamental.count("margin") == 2
    assert fundamental.count("earnings") == 24
    assert fundamental.count("index_valuation") == 5
    assert fundamental.count("index_fallback") == 0
    assert len(fundamental) == 39
    assert len(technical) == 12
    assert len(technical) + len(fundamental) == 51


@pytest.mark.unit
def test_fundamentals_mode_falls_back_for_all_five_indexes(monkeypatch, tmp_path):
    technical: list[str] = []
    fundamental: list[str] = []
    _install_technical(monkeypatch, technical)
    _install_fundamentals(monkeypatch, fundamental, primary_ok=False)
    _install_llm(monkeypatch, tmp_path)

    from cli.run import run_market

    path = run_market(DAY, fundamentals=True)

    assert path.exists()
    assert fundamental.count("index_valuation") == 5
    assert fundamental.count("index_fallback") == 5
    assert len(fundamental) == 44
    assert len(technical) == 12
    assert len(technical) + len(fundamental) == 56
