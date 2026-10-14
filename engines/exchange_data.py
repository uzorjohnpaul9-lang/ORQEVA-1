"""Keyless crypto OHLC data from public exchange APIs.

Tries several free, key-less spot kline endpoints so crypto charts work
regardless of which exchanges a given host can reach. Binance/Bybit block
US cloud IPs, so US-reachable venues (Binance.US, Coinbase, OKX) are also
in the chain. Every function returns empty results on failure and never
raises; callers fall back to Twelve Data.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

TIMEOUT = (4, 10)  # (connect, read) seconds
COOLDOWN = 600  # skip a provider this long after a network failure

BINANCE_BASE = "https://api.binance.com"
BINANCE_US_BASE = "https://api.binance.us"
BYBIT_BASE = "https://api.bybit.com"
COINBASE_BASE = "https://api.exchange.coinbase.com"
OKX_BASE = "https://www.okx.com"

_BINANCE_INTERVALS = {
    "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
    "1h": "1h", "4h": "4h", "1day": "1d", "1week": "1w",
}
_BYBIT_INTERVALS = {
    "1min": "1", "5min": "5", "15min": "15", "30min": "30",
    "1h": "60", "4h": "240", "1day": "D", "1week": "W",
}
_COINBASE_GRANULARITY = {
    "1min": 60, "5min": 300, "15min": 900, "30min": 1800,
    "1h": 3600, "1day": 86400,
}
_OKX_INTERVALS = {
    "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
    "1h": "1H", "4h": "4H", "1day": "1D", "1week": "1W",
}

# Skip a provider this long after a network failure (geo-block) so chart
# requests do not pay the connection timeout on every call.
_down_until: dict[str, float] = {}


def _base_quote(symbol: str) -> tuple[str, str]:
    s = symbol.upper().replace("-", "/").replace("_", "/")
    if "/" in s:
        base, quote = s.split("/", 1)
        return base, quote
    for q in ("USDT", "USDC", "USD"):
        if s.endswith(q):
            return s[: -len(q)], q
    return s, "USD"


def _usdt_pair(symbol: str) -> str:
    base, _ = _base_quote(symbol)
    return f"{base}USDT"


def _dashed(symbol: str, quote: str) -> str:
    base, _ = _base_quote(symbol)
    return f"{base}-{quote}"


def to_pair(symbol: str) -> str:
    """Map an internal symbol to an exchange pair: BTC/USD -> BTCUSDT."""
    return _usdt_pair(symbol)


def _ms_to_iso(ms: Any) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return ""


def _ohlc(time_v: str, o: Any, h: Any, l: Any, c: Any) -> dict[str, Any]:
    return {"time": time_v, "open": float(o), "high": float(h), "low": float(l), "close": float(c)}


def _parse_binance(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    return [_ohlc(_ms_to_iso(k[0]), k[1], k[2], k[3], k[4]) for k in data if isinstance(k, list) and len(k) >= 5]


def _parse_bybit(data: Any) -> list[dict[str, Any]]:
    rows = (data.get("result") or {}).get("list") or [] if isinstance(data, dict) else []
    bars = [_ohlc(_ms_to_iso(k[0]), k[1], k[2], k[3], k[4]) for k in rows if isinstance(k, list) and len(k) >= 5]
    bars.reverse()  # newest-first -> oldest-first
    return bars


def _parse_coinbase(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    # [time, low, high, open, close, volume], newest-first
    bars = [_ohlc(_ms_to_iso(r[0]), r[3], r[2], r[1], r[4]) for r in data if isinstance(r, list) and len(r) >= 5]
    bars.reverse()
    return bars


def _parse_okx(data: Any) -> list[dict[str, Any]]:
    rows = data.get("data") or [] if isinstance(data, dict) else []
    bars = [_ohlc(_ms_to_iso(k[0]), k[1], k[2], k[3], k[4]) for k in rows if isinstance(k, list) and len(k) >= 5]
    bars.reverse()
    return bars


_PROVIDERS: dict[str, dict[str, Any]] = {
    "binance": {
        "base": BINANCE_BASE,
        "intervals": _BINANCE_INTERVALS,
        "path": "/api/v3/klines",
        "params": lambda pair, iv, limit: {"symbol": pair, "interval": iv, "limit": limit},
        "pair": _usdt_pair,
        "parse": _parse_binance,
    },
    "binance_us": {
        "base": BINANCE_US_BASE,
        "intervals": _BINANCE_INTERVALS,
        "path": "/api/v3/klines",
        "params": lambda pair, iv, limit: {"symbol": pair, "interval": iv, "limit": limit},
        "pair": _usdt_pair,
        "parse": _parse_binance,
    },
    "bybit": {
        "base": BYBIT_BASE,
        "intervals": _BYBIT_INTERVALS,
        "path": "/v5/market/kline",
        "params": lambda pair, iv, limit: {"category": "spot", "symbol": pair, "interval": iv, "limit": limit},
        "pair": _usdt_pair,
        "parse": _parse_bybit,
    },
    "coinbase": {
        "base": COINBASE_BASE,
        "intervals": _COINBASE_GRANULARITY,
        "path": "/products/{pair}/candles",
        "params": lambda pair, iv, limit: {"granularity": iv},
        "pair": lambda symbol: _dashed(symbol, "USD"),
        "parse": _parse_coinbase,
    },
    "okx": {
        "base": OKX_BASE,
        "intervals": _OKX_INTERVALS,
        "path": "/api/v5/market/candles",
        "params": lambda pair, iv, limit: {"instId": pair, "bar": iv, "limit": limit},
        "pair": _usdt_pair,
        "parse": _parse_okx,
    },
}

DEFAULT_ORDER = ("binance", "binance_us", "bybit", "coinbase", "okx")


def _request(cfg: dict[str, Any], pair: str, iv: Any, limit: int) -> list[dict[str, Any]]:
    url = f"{cfg['base']}{cfg['path'].format(pair=pair)}"
    r = requests.get(url, params=cfg["params"](pair, iv, min(limit, 1000)), timeout=TIMEOUT)
    return cfg["parse"](r.json())


def fetch_one(name: str, symbol: str, interval: str, limit: int = 120) -> list[dict[str, Any]]:
    """Fetch bars from a single provider (ignores cooldown). [] on any failure."""
    cfg = _PROVIDERS.get(name)
    if not cfg:
        return []
    iv = cfg["intervals"].get(interval)
    if iv is None:
        return []
    pair = cfg["pair"](symbol)
    try:
        return _request(cfg, pair, iv, limit)
    except Exception as e:
        logger.warning("%s klines failed for %s: %s", name, pair, str(e)[:120])
        return []


def _binance_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    return fetch_one("binance", symbol, interval, limit)


def _bybit_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    return fetch_one("bybit", symbol, interval, limit)


def fetch_klines(
    symbol: str,
    interval: str = "1day",
    limit: int = 120,
    providers: tuple[str, ...] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Try providers in order. Returns (bars, source) or ([], None)."""
    for name in (providers or DEFAULT_ORDER):
        if time.time() < _down_until.get(name, 0.0):
            continue
        cfg = _PROVIDERS.get(name)
        if not cfg or cfg["intervals"].get(interval) is None:
            continue
        pair = cfg["pair"](symbol)
        try:
            bars = _request(cfg, pair, cfg["intervals"][interval], limit)
        except Exception as e:
            logger.warning("%s klines failed for %s: %s", name, pair, str(e)[:120])
            _down_until[name] = time.time() + COOLDOWN
            continue
        if bars:
            return bars, name
    return [], None


def fetch_prices(symbol: str, lookback: int = 90, interval: str = "1day") -> list[float]:
    """Closing prices for indicator math. Empty list when all providers fail."""
    bars, _ = fetch_klines(symbol, interval, lookback)
    return [b["close"] for b in bars]


def probe(symbol: str = "BTC/USD", interval: str = "1day", limit: int = 3) -> list[dict[str, Any]]:
    """Diagnostic: test every provider from this host. Never raises."""
    out: list[dict[str, Any]] = []
    for name in DEFAULT_ORDER:
        t = time.time()
        bars = fetch_one(name, symbol, interval, limit)
        out.append({
            "provider": name,
            "ok": bool(bars),
            "bars": len(bars),
            "latency_ms": int((time.time() - t) * 1000),
            "last_close": bars[-1]["close"] if bars else None,
        })
    return out
