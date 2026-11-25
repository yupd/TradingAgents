"""Outbound HTTP for the A-share sources: browser headers, Eastmoney pacing, retries."""

from __future__ import annotations

import time

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.eastmoney.com/",
}

_MIN_EM_INTERVAL = 0.5
_last_em_request = 0.0


def em_get(url: str, params: dict | None = None, timeout: int = 15, retries: int = 3):
    """GET with the browser headers, Eastmoney pacing and exponential backoff."""
    global _last_em_request
    for attempt in range(retries):
        if "eastmoney.com" in url:
            elapsed = time.time() - _last_em_request
            if elapsed < _MIN_EM_INTERVAL:
                time.sleep(_MIN_EM_INTERVAL - elapsed)
            _last_em_request = time.time()
        try:
            return requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.0 * (2 ** attempt))
    raise RuntimeError("unreachable")
