from brief.fetch import StockFacts
from brief.rules import compute_flags
from tradingagents.dataflows.vendors.a_share.types import DailyBar, Snapshot


def _snap(**kw):
    base = dict(code="600519", name="贵州茅台", price=10.0, prev_close=9.0, change_pct=0.0,
                volume=1000.0, turnover_rate=1.0, pe_ttm=20.0, pb=3.0,
                source="mootdx", as_of="2026-11-25 15:00")
    base.update(kw)
    return Snapshot(**base)


def _bars(volumes):
    return [DailyBar(date=f"2026-10-{i + 1:02d}", open=9.0, high=9.5, low=8.9, close=9.0,
                     volume=v, source="mootdx", as_of="2026-11-25 15:00")
            for i, v in enumerate(volumes)]


def facts(**kw):
    base = dict(code="600519", name="贵州茅台", quote=None, bars=[], announcements=[],
                reports=[], fund_flow="", lockup="", missing=[])
    base.update(kw)
    return StockFacts(**base)


def test_limit_up_flag():
    flags = compute_flags(facts(quote=_snap(change_pct=10.0)))
    assert any(f.kind == "limit_up" for f in flags)


def test_volume_spike_flag():
    flags = compute_flags(facts(quote=_snap(volume=3000), bars=_bars([1000] * 20)))
    assert any(f.kind == "volume_spike" for f in flags)


def test_missing_data_is_reported():
    flags = compute_flags(facts(missing=["quote", "fund_flow"]))
    assert any(f.kind == "data_missing" and "quote" in f.detail for f in flags)
