"""A-share code normalization: every common spelling of one code becomes one symbol."""

from __future__ import annotations

import re

from .types import AStockSymbol

_EXCHANGE = r"(SH|SZ|BJ)"
_CODE = r"(\d{6})"
_PATTERN = re.compile(rf"^(?:{_EXCHANGE})?{_CODE}(?:\.(SH|SS|SZ|BJ))?$")


def _infer_exchange(code: str) -> str:
    if code[0] in "69":
        return "SH"          # 6xxxxx main board, 9xxxxx Shanghai B shares
    if code[0] in "023":
        return "SZ"          # 0/3 main and ChiNext, 2xxxxx Shenzhen B shares
    if code[0] in "48":
        return "BJ"          # Beijing Stock Exchange
    raise ValueError(f"cannot infer the exchange of A-share code {code!r}")


def parse_ashare(raw: str) -> AStockSymbol:
    """Read ``600519``, ``SH600519``, ``600519.SH`` or ``600519.SS`` as one symbol.

    Raises ``ValueError`` for anything that is not a six-digit mainland code.
    An explicit exchange prefix or suffix wins over the code's board prefix.
    """
    text = (raw or "").strip().upper()
    match = _PATTERN.match(text)
    if match is None:
        raise ValueError(f"not an A-share code: {raw!r}")
    prefix, code, suffix = match.groups()
    exchange = prefix or suffix or _infer_exchange(code)
    if exchange == "SS":
        exchange = "SH"
    return AStockSymbol(code=code, exchange=exchange)
