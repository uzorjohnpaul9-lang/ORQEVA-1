"""Keyless crypto OHLC data from public exchange APIs (Binance, Bybit).

Both expose free, key-less spot kline endpoints. Binance is geo-restricted in
some regions (HTTP 451 / no route), so Bybit is tried next; callers can then
fall back to Twelve Data. Every function returns empty results on failure and
never raises.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com"
BYBIT_BASE = "https://api.bybit.com"

# Twelve-Data-style interval -> exchange interval
_BINANCE_INTERVALS = {
    "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
    "1h": "1h", "4h": "4h", "1day": "1d", "1week": "1w",
}
_BYBIT_INTERVALS = {
    "1min": "1", "5min": "5", "15min": "15", "30min": "30",
    "1h": "60", "4h": "240", "1day": "D", "1week": "W",
}

# After a Binance failure (geo-block), skip it for a while so chart requests
# do not pay the connection timeout on every call.
_BINANCE_COOLDOWN = 900  # seconds
_binance_down_until = 0.0


def to_pair(symbol: str) -> str:
    """Map an internal symbol to an exchange pair: BTC/USD -> BTCUSDT."""
    s = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
    if s.endswith("USDT"):
        return s
    if s.endswith("USD"):
        return s + "T"
    return s


def _ms_to_iso(ms: Any) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return ""


def _binance_klines(pair: str, interval: str, limit: int) -> list[dict[str, Any]]:
    iv = _BINANCE_INTERVALS.get(interval)
    global _binance_down_until
    if not iv or time.time() < _binance_down_until:
        return []
    try:
        r = requests.get(
            f"{BINANCE_BASE}/api/v3/klines",
            params={"symbol": pair, "interval": iv, "limit": min(limit, 1000)},
            timeout=5,
        )
        data = r.json()
    except Exception as e:
        logger.warning("Binance klines failed for %s: %s", pair, str(e)[:120])
        _binance_down_until = time.time() + _BINANCE_COOLDOWN
        return []
    if not isinstance(data, list):
        _binance_down_until = time.time() + _BINANCE_COOLDOWN
        return []
    return [
        {
            "time": _ms_to_iso(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
        }
        for k in data
        if isinstance(k, list) and len(k) >= 5
    ]


def _bybit_klines(pair: str, interval: str, limit: int) -> list[dict[str, Any]]:
    iv = _BYBIT_INTERVALS.get(interval)
    if not iv:
        return []
    try:
        r = requests.get(
            f"{BYBIT_BASE}/v5/market/kline",
            params={"category": "spot", "symbol": pair, "interval": iv, "limit": min(limit, 1000)},
            timeout=10,
        )
        data = r.json()
    except Exception as e:
        logger.warning("Bybit kline failed for %s: %s", pair, str(e)[:120])
        return []
    rows = (data.get("result") or {}).get("list") or []
    bars = [
        {
            "time": _ms_to_iso(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
        }
        for k in rows
        if isinstance(k, list) and len(k) >= 5
    ]
    bars.reverse()  # Bybit returns newest-first
    return bars


def fetch_klines(
    symbol: str,
    interval: str = "1day",
    limit: int = 120,
) -> tuple[list[dict[str, Any]], str | None]:
    """Try Binance then Bybit. Returns (bars, source) or ([], None)."""
    pair = to_pair(symbol)
    bars = _binance_klines(pair, interval, limit)
    if bars:
        return bars, "binance"
    bars = _bybit_klines(pair, interval, limit)
    if bars:
        return bars, "bybit"
    return [], None


def fetch_prices(symbol: str, lookback: int = 90, interval: str = "1day") -> list[float]:
    """Closing prices for indicator math. Empty list when both sources fail."""
    bars, _ = fetch_klines(symbol, interval, lookback)
    return [b["close"] for b in bars]
