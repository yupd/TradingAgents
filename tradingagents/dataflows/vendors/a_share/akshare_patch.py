"""Pace and header AkShare's Eastmoney calls, without touching other traffic.

AkShare reaches Eastmoney through its own ``requests.get``; our explicit
``http.em_get`` never sees those calls. Importing this module installs a narrow
wrapper that only changes Eastmoney URLs: browser headers, the shared 0.5s
spacing and three backoff retries. Set ``TRADINGAGENTS_AKSHARE_PATCH=0`` to skip
the install.
"""

from __future__ import annotations

import logging
import os

import requests

from . import http

logger = logging.getLogger(__name__)
_installed = False
_RETRIES = 3


def _is_eastmoney(url: str) -> bool:
    return "eastmoney.com" in str(url)


def _wrap(get):
    """Wrap a ``requests.get``-shaped callable with the Eastmoney policy."""

    def patched(url: str, **kwargs):
        if not _is_eastmoney(url):
            return get(url, **kwargs)
        headers = dict(kwargs.get("headers") or {})
        for key, value in http._HEADERS.items():
            headers.setdefault(key, value)
        kwargs["headers"] = headers
        for attempt in range(_RETRIES):
            http.throttle(url)
            try:
                return get(url, **kwargs)
            except Exception:
                if attempt == _RETRIES - 1:
                    raise
        raise RuntimeError("unreachable")

    return patched


def install() -> bool:
    """Install the wrapper once; returns whether this call installed it."""
    global _installed
    if _installed or os.getenv("TRADINGAGENTS_AKSHARE_PATCH", "1") == "0":
        return False
    requests.get = _wrap(requests.get)
    _installed = True
    logger.info("AkShare Eastmoney patch installed: headers + pacing + retries")
    return True


install()
