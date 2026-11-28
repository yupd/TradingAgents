"""A-share daily bars, snapshots and indicators, with a fixed fallback chain."""

from __future__ import annotations

import pandas as pd

from . import http
from .format import format_bars, format_patterns
from .patterns import TREND_LOOKBACK, detect_patterns
from .types import AStockSymbol, DailyBar, Snapshot

_OHLCV = ("date", "open", "high", "low", "close", "volume")


def _prefix(sym: AStockSymbol) -> str:
    return {"SH": "sh", "SZ": "sz", "BJ": "bj"}[sym.exchange]


def _market_id(sym: AStockSymbol) -> str:
    return "1" if sym.exchange == "SH" else "0"


def _to_bars(frame: pd.DataFrame, source: str, start: str, end: str) -> list[DailyBar]:
    if frame is None or frame.empty:
        return []
    df = frame.copy()
    df = df.rename(columns={"vol": "volume", "datetime": "date"})
    if "date" not in df.columns:
        df = df.reset_index().rename(columns={"index": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    bars = []
    for row in df.itertuples(index=False):
        bars.append(DailyBar(date=row.date, open=float(row.open), high=float(row.high),
                             low=float(row.low), close=float(row.close),
                             volume=float(row.volume), source=source, as_of=row.date))
    return bars


def _mootdx_bars(sym: AStockSymbol, start: str, end: str) -> pd.DataFrame:
    from mootdx.quotes import Quotes

    client = Quotes.factory(market="std", multithread=True, heartbeat=True)
    frame = client.bars(symbol=sym.code, frequency=9, offset=800)
    if frame is None:
        raise RuntimeError("mootdx returned nothing")
    return frame.rename(columns={"datetime": "date"})


def _em_bars(sym: AStockSymbol, start: str, end: str) -> pd.DataFrame:
    response = http.em_get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": f"{_market_id(sym)}.{sym.code}",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56",
            "klt": 101, "fqt": 1,
            "beg": start.replace("-", ""), "end": end.replace("-", ""),
        },
    )
    data = response.json().get("data") or {}
    klines = data.get("klines") or []
    rows = [line.split(",")[:6] for line in klines]
    return pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume"])


def _tencent_bars(sym: AStockSymbol, start: str, end: str) -> pd.DataFrame:
    symbol = f"{_prefix(sym)}{sym.code}"
    response = http.em_get(
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
        params={"param": f"{symbol},day,{start},{end},640,qfq"},
    )
    data = response.json().get("data", {}).get(symbol, {})
    rows = data.get("qfqday") or data.get("day") or []
    rows = [row[:6] for row in rows]
    return pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume"])


def _sina_bars(sym: AStockSymbol, start: str, end: str) -> pd.DataFrame:
    symbol = f"{_prefix(sym)}{sym.code}"
    response = http.em_get(
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/x/CN_MarketDataService.getKLineData",
        params={"symbol": symbol, "scale": 240, "ma": "no", "datalen": 1023},
    )
    text = response.text
    payload = text[text.index("(") + 1:text.rindex(")")]
    frame = pd.read_json(payload)
    return frame.rename(columns={"day": "date"})[["date", "open", "high", "low", "close", "volume"]]


def get_daily_bars(sym: AStockSymbol, start: str, end: str) -> list[DailyBar]:
    """The first source that returns bars wins; all failures raise."""
    errors = []
    for source, fetch in (("mootdx", _mootdx_bars), ("eastmoney", _em_bars),
                          ("tencent", _tencent_bars), ("sina", _sina_bars)):
        try:
            bars = _to_bars(fetch(sym, start, end), source, start, end)
            if bars:
                return bars
            errors.append(f"{source}: no rows")
        except Exception as exc:
            errors.append(f"{source}: {type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(errors))


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    from .symbols import parse_ashare

    sym = parse_ashare(symbol)
    try:
        bars = get_daily_bars(sym, start_date, end_date)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: no A-share price source answered for {sym.display} ({exc})"
    return format_bars(sym, bars)


def _tencent_snapshot(sym: AStockSymbol) -> Snapshot:
    response = http.em_get(f"https://qt.gtimg.cn/q={_prefix(sym)}{sym.code}")
    payload = response.text.split('"')[1]
    f = payload.split("~")
    price, prev = float(f[3]), float(f[4])
    change = ((price / prev) - 1) * 100 if prev else 0.0
    def number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return Snapshot(code=sym.code, name=f[1], price=price, prev_close=prev,
                    change_pct=change, volume=number(f[6]) or 0.0,
                    turnover_rate=number(f[38]), pe_ttm=number(f[39]), pb=number(f[46]),
                    source="tencent", as_of=f[30])


def get_snapshot(sym: AStockSymbol) -> Snapshot:
    """Live snapshot only; historical runs use get_verified_market_snapshot."""
    return _tencent_snapshot(sym)


def _indicator_frame(bars: list[DailyBar]) -> pd.DataFrame:
    return pd.DataFrame({
        "date": [b.date for b in bars],
        "open": [b.open for b in bars], "high": [b.high for b in bars],
        "low": [b.low for b in bars], "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    })


_INDICATORS = {"rsi": "rsi_14", "macd": "macd", "boll": "boll",
               "ma": "close_20_sma", "ema": "close_20_ema", "atr": "atr_14",
               "kdj": "kdjk", "kdj_k": "kdjk", "kdj_d": "kdjd", "kdj_j": "kdjj",
               # Names market_analyst offers; stockstats uses the same column names.
               "close_50_sma": "close_50_sma", "close_200_sma": "close_200_sma",
               "close_10_ema": "close_10_ema", "macds": "macds", "macdh": "macdh",
               "boll_ub": "boll_ub", "boll_lb": "boll_lb", "vwma": "vwma"}


# stockstats fills leading values from an expanding window, so a short history
# yields a number that is not the indicator its column name promises.
_MIN_BARS = {"close_50_sma": 50, "close_200_sma": 200, "close_10_ema": 10,
             "macd": 26, "macds": 35, "macdh": 35, "rsi_14": 15,
             "boll": 20, "boll_ub": 20, "boll_lb": 20, "atr_14": 15,
             "vwma": 20, "close_20_sma": 20, "close_20_ema": 20,
             "kdjk": 9, "kdjd": 9, "kdjj": 9}


def _stockstats(bars: list[DailyBar]):
    from stockstats import StockDataFrame

    return StockDataFrame.retype(_indicator_frame(bars))


def _bars_until(symbol: str, curr_date: str) -> list[DailyBar]:
    from .symbols import parse_ashare

    sym = parse_ashare(symbol)
    bars = get_daily_bars(sym, "1990-01-01", curr_date)
    return [b for b in bars if b.date <= curr_date]


def get_indicators(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    key = indicator.strip().lower()
    column = _INDICATORS.get(key)
    if column is None:
        return f"UNSUPPORTED_INDICATOR: {indicator}"
    requested = look_back_days if look_back_days > 0 else 30
    try:
        bars = _bars_until(symbol, curr_date)
        if not bars:
            return f"DATA_UNAVAILABLE: no bars for {symbol} up to {curr_date}"
        needed = _MIN_BARS.get(column, 0)
        if len(bars) < needed:
            return (f"DATA_UNAVAILABLE: {key} needs at least {needed} bars, "
                    f"got {len(bars)}")
        frame = _stockstats(bars)
        # Skip bars whose window is still partial; stockstats would otherwise
        # fill them with expanding-window means labelled as the full indicator.
        series = frame[column].iloc[max(needed - 1, 0):].dropna().tail(requested)
    except Exception as exc:
        return f"DATA_UNAVAILABLE: indicators for {symbol} failed ({exc})"
    # StockDataFrame indexes rows by date, so the date travels with the value
    # even when dropna() removes a row from the middle.
    rows = [[str(i), f"{float(value):.4f}"] for i, value in series.items()]
    table = "\n".join(f"| {d} | {v} |" for d, v in rows)
    return (f"# {symbol} {key.upper()}\n\n| Date | Value |\n|---|---|\n{table}\n\n"
            f"Source: {bars[-1].source} | As of: {bars[-1].date}")


def get_kline_patterns(symbol: str, curr_date: str, look_back_days: int = 60) -> str:
    """Deterministic candlestick patterns over the window ending at curr_date."""
    from .symbols import parse_ashare

    sym = parse_ashare(symbol)
    try:
        bars = _bars_until(symbol, curr_date)
    except Exception as exc:
        return (f"DATA_UNAVAILABLE: no A-share price source answered "
                f"for {sym.display} ({exc})")
    if not bars:
        return f"DATA_UNAVAILABLE: no bars for {sym.display} up to {curr_date}"
    requested = look_back_days if look_back_days > 0 else 60
    if requested < len(bars):
        start = len(bars) - requested
        # Trend rules read 6 bars before a candidate; keep them as context so
        # the first bars of the requested window are not silently context-free.
        scan = detect_patterns(bars[max(0, start - (TREND_LOOKBACK + 1)):])
        window_start = bars[start].date
        hits = tuple(hit for hit in scan.hits if hit.date >= window_start)
    else:
        scan = detect_patterns(bars)
        hits = scan.hits
    return format_patterns(sym, hits, bars[-1].source, bars[-1].date,
                           min(requested, len(bars)), scan.skipped)


def get_verified_market_snapshot(symbol: str, curr_date: str, look_back_days: int = 30) -> str:
    """A point-in-time snapshot built from closes, never from the live quote."""
    try:
        bars = _bars_until(symbol, curr_date)
        if not bars:
            return f"DATA_UNAVAILABLE: no bars for {symbol} up to {curr_date}"
        frame = _stockstats(bars)
        last = bars[-1]
        ma20 = float(frame["close_20_sma"].iloc[-1])
        rsi = float(frame["rsi_14"].iloc[-1])
        macd = float(frame["macd"].iloc[-1])
        recent = ", ".join(f"{b.date}:{b.close:.2f}" for b in bars[-min(look_back_days, len(bars)):])
    except Exception as exc:
        return f"DATA_UNAVAILABLE: snapshot for {symbol} failed ({exc})"
    return (f"# {symbol} verified snapshot as of {last.date}\n\n"
            f"- Close: {last.close:.2f}\n- MA20: {ma20:.2f}\n- RSI14: {rsi:.2f}\n"
            f"- MACD: {macd:.4f}\n- Recent closes: {recent}\n\n"
            f"Source: {last.source} | As of: {last.date}")
