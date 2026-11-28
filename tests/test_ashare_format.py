from tradingagents.dataflows.vendors.a_share.format import format_bars, format_snapshot
from tradingagents.dataflows.vendors.a_share.symbols import parse_ashare
from tradingagents.dataflows.vendors.a_share.types import DailyBar, Snapshot

SYM = parse_ashare("600519")


def _bars():
    return [DailyBar(date="2026-11-27", open=1469.99, high=1481.41, low=1452.99,
                     close=1472.36, volume=39808, source="eastmoney", as_of="2026-11-27")]


def test_format_bars_labels_volume_in_lots():
    text = format_bars(SYM, _bars())
    assert "单位：元、手" in text


def test_snapshot_and_bars_share_volume_unit():
    snap = Snapshot(code="600519", name="贵州茅台", price=1472.36, prev_close=1469.99,
                    change_pct=0.16, volume=39808, turnover_rate=1.0, pe_ttm=20.0,
                    pb=3.0, source="tencent", as_of="2026-11-27 15:00")
    snapshot_text = format_snapshot(SYM, snap)
    volume_row = next(line for line in snapshot_text.splitlines() if "成交量" in line)
    assert "手" in volume_row
    assert "单位：元、手" in format_bars(SYM, _bars())
