"""Keyless traditional-finance OHLC data (stocks, forex, commodities).

Mirrors engines.exchange_data: a provider chain with a per-provider cooldown so
a network failure (or a geo-block) does not cost the connection timeout on
every call. Yahoo Finance gives full OHLC for equities, FX and metals/energy
futures; Stooq is a CSV fallback; Frankfurter supplies close-only FX history as
a last resort. Every function returns empty results on failure and never
raises; callers fall back to Twelve Data and finally to simulated data.
"""
from __future__ import annotations

import csv
import io
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

TIMEOUT = (4, 12)  # (connect, read) seconds
COOLDOWN = 600  # skip a provider this long after a network failure

YAHOO_BASE = "https://query1.finance.yahoo.com"
STOOQ_BASE = "https://stooq.com"
FRANKFURTER_BASE = "https://api.frankfurter.app"

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ORQEVA/1.0)"}

# Internal interval -> Yahoo chart interval. Yahoo has no 4h; it is skipped.
_YAHOO_INTERVALS = {
    "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
    "1h": "60m", "1day": "1d", "1week": "1wk",
}
_YAHOO_RANGE = {"1min": "5d", "5min": "1mo", "15min": "1mo", "30min": "1mo", "1h": "3mo"}

# Commodity spot symbol -> front-month futures ticker.
_COMMODITY_YAHOO = {
    "XAU/USD": "GC=F", "XAG/USD": "SI=F", "WTI/USD": "CL=F",
    "BRENT/USD": "BZ=F", "NATGAS/USD": "NG=F",
}
_COMMODITY_STOOQ = {
    "XAU/USD": "xauusd", "XAG/USD": "xagusd", "WTI/USD": "cl.f",
    "BRENT/USD": "cb.f", "NATGAS/USD": "ng.f",
}

# Skip a provider this long after a network failure (geo-block) so chart
# requests do not pay the connection timeout on every call.
_down_until: dict[str, float] = {}


def _norm(symbol: str) -> str:
    return symbol.upper().replace("-", "/").replace("_", "/")


def _yahoo_symbol(symbol: str, market: str) -> str | None:
    s = _norm(symbol)
    if market == "forex":
        base, quote_ = _fx_pair(s)
        return f"{base}{quote_}=X" if base else None
    if market == "commodity":
        if s in _COMMODITY_YAHOO:
            return _COMMODITY_YAHOO[s]
        return s if "=" in s else None
    return s.replace("/", "-") or None


def _stooq_symbol(symbol: str, market: str) -> str | None:
    s = _norm(symbol)
    if market == "forex":
        base, quote_ = _fx_pair(s)
        return f"{base}{quote_}".lower() if base else None
    if market == "commodity":
        return _COMMODITY_STOOQ.get(s)
    return f"{s.lower()}.us" if s else None


def _fx_pair(symbol: str) -> tuple[str, str]:
    s = _norm(symbol)
    if s.count("/") == 1:
        base, quote_ = s.split("/", 1)
        if base and quote_:
            return base, quote_
    return "", ""


def _epoch_to_iso(sec: Any) -> str:
    try:
        return datetime.fromtimestamp(int(sec), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return ""


def _ohlc(time_v: str, o: Any, h: Any, l: Any, c: Any) -> dict[str, Any]:
    return {"time": time_v, "open": float(o), "high": float(h), "low": float(l), "close": float(c)}


def _parse_yahoo(data: Any, limit: int) -> list[dict[str, Any]]:
    try:
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return []
        r = result[0]
        stamps = r.get("timestamp") or []
        quote_ = ((r.get("indicators") or {}).get("quote") or [{}])[0]
        opens = quote_.get("open") or []
        highs = quote_.get("high") or []
        lows = quote_.get("low") or []
        closes = quote_.get("close") or []
        bars = []
        for i in range(min(len(stamps), len(opens), len(highs), len(lows), len(closes))):
            if None in (opens[i], highs[i], lows[i], closes[i]):
                continue
            bars.append(_ohlc(_epoch_to_iso(stamps[i]), opens[i], highs[i], lows[i], closes[i]))
        return bars[-limit:]
    except (AttributeError, TypeError, ValueError):
        return []


def _parse_stooq(text: str, limit: int) -> list[dict[str, Any]]:
    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except Exception:
        return []
    bars = []
    for r in rows:
        try:
            bars.append({
                "time": r["Date"],
                "open": float(r["Open"]),
                "high": float(r["High"]),
                "low": float(r["Low"]),
                "close": float(r["Close"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return bars[-limit:]


def _yahoo_bars(symbol: str, interval: str, limit: int, market: str) -> list[dict[str, Any]]:
    ysym = _yahoo_symbol(symbol, market)
    yiv = _YAHOO_INTERVALS.get(interval)
    if not ysym or not yiv:
        return []
    rng = _YAHOO_RANGE.get(interval) or ("5y" if interval in ("1day", "1week") else "1mo")
    url = f"{YAHOO_BASE}/v8/finance/chart/{quote(ysym, safe='')}"
    r = requests.get(url, params={"interval": yiv, "range": rng}, headers=_HEADERS, timeout=TIMEOUT)
    return _parse_yahoo(r.json(), limit)


def _stooq_bars(symbol: str, interval: str, limit: int, market: str) -> list[dict[str, Any]]:
    if interval not in ("1day", "1week"):
        return []
    ssym = _stooq_symbol(symbol, market)
    if not ssym:
        return []
    r = requests.get(f"{STOOQ_BASE}/q/d/l/", params={"s": ssym, "i": "d"}, headers=_HEADERS, timeout=TIMEOUT)
    return _parse_stooq(r.text, limit)


_BAR_PROVIDERS = {"yahoo": _yahoo_bars, "stooq": _stooq_bars}

DEFAULT_ORDER = ("yahoo", "stooq")


def fetch_bars(
    symbol: str,
    interval: str = "1day",
    limit: int = 120,
    market: str = "stock",
    providers: tuple[str, ...] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Try providers in order. Returns (bars, source) or ([], None)."""
    for name in (providers or DEFAULT_ORDER):
        if time.time() < _down_until.get(name, 0.0):
            continue
        fn = _BAR_PROVIDERS.get(name)
        if not fn:
            continue
        try:
            bars = fn(symbol, interval, limit, market)
        except Exception as e:
            logger.warning("%s bars failed for %s: %s", name, symbol, str(e)[:120])
            _down_until[name] = time.time() + COOLDOWN
            continue
        if bars:
            return bars, name
    return [], None


def _frankfurter_closes(symbol: str, lookback: int) -> list[float]:
    base, quote_ = _fx_pair(symbol)
    if not base or not quote_:
        return []
    start = (datetime.now(timezone.utc) - timedelta(days=lookback + 10)).strftime("%Y-%m-%d")
    url = f"{FRANKFURTER_BASE}/{start}.."
    r = requests.get(url, params={"from": base, "to": quote_}, headers=_HEADERS, timeout=TIMEOUT)
    rates = (r.json() or {}).get("rates") or {}
    closes = []
    for day in sorted(rates):
        value = rates[day].get(quote_)
        if value is not None:
            closes.append(float(value))
    return closes[-lookback:]


def fetch_closes(
    symbol: str,
    lookback: int = 90,
    market: str = "stock",
    interval: str = "1day",
) -> tuple[list[float], str | None]:
    """Closing prices + source. Frankfurter close-only fallback for forex."""
    bars, source = fetch_bars(symbol, interval, lookback, market)
    if bars:
        return [b["close"] for b in bars], source
    if market == "forex":
        try:
            closes = _frankfurter_closes(symbol, lookback)
        except Exception as e:
            logger.warning("frankfurter closes failed for %s: %s", symbol, str(e)[:120])
            closes = []
        if closes:
            return closes, "frankfurter"
    return [], None


def fetch_prices(symbol: str, lookback: int = 90, market: str = "stock", interval: str = "1day") -> list[float]:
    """Closing prices for indicator math. Empty list when all providers fail."""
    closes, _ = fetch_closes(symbol, lookback, market, interval)
    return closes


def fetch_quote(symbol: str, market: str = "stock") -> dict[str, Any] | None:
    """Keyless snapshot quote via Yahoo chart meta. None on failure."""
    ysym = _yahoo_symbol(symbol, market)
    if not ysym:
        return None
    try:
        url = f"{YAHOO_BASE}/v8/finance/chart/{quote(ysym, safe='')}"
        r = requests.get(url, params={"interval": "1d", "range": "5d"}, headers=_HEADERS, timeout=TIMEOUT)
        result = (r.json().get("chart") or {}).get("result") or []
        if not result:
            return None
        meta = result[0].get("meta") or {}
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose")
        if prev is None:
            prev = meta.get("previousClose")
        if price is None:
            return None
        change = float(price) - float(prev) if prev is not None else 0.0
        change_pct = (change / float(prev) * 100.0) if prev else 0.0
        return {
            "symbol": symbol,
            "price": round(float(price), 6),
            "change": round(change, 6),
            "change_percent": round(change_pct, 4),
            "source": "yahoo",
        }
    except (AttributeError, TypeError, ValueError) as e:
        logger.warning("yahoo quote failed for %s: %s", symbol, str(e)[:120])
        return None


def probe(symbol: str = "AAPL", interval: str = "1day", limit: int = 3, market: str = "stock") -> list[dict[str, Any]]:
    """Diagnostic: test every provider from this host. Never raises."""
    out: list[dict[str, Any]] = []
    for name in DEFAULT_ORDER:
        t = time.time()
        fn = _BAR_PROVIDERS[name]
        try:
            bars = fn(symbol, interval, limit, market)
        except Exception:
            bars = []
        out.append({
            "provider": name,
            "ok": bool(bars),
            "bars": len(bars),
            "latency_ms": int((time.time() - t) * 1000),
            "last_close": bars[-1]["close"] if bars else None,
        })
    return out
