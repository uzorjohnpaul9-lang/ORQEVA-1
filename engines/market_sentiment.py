"""Keyless crypto market-sentiment feeds (Phase H).

Order-flow imbalance, derivatives funding/open interest, Fear & Greed and
BTC dominance, all from free public endpoints. Mirrors exchange_data.py:
per-provider cooldown after network failures, and every function returns a
graceful empty/None result - never raises. Sentiment is a *quality dial*
(confidence modifier + confirmation tag), not a signal source.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

TIMEOUT = (4, 10)  # (connect, read) seconds
COOLDOWN = 600      # skip a provider this long after a network failure
CACHE_TTL = 900     # 15 minutes sentiment cache

BINANCE_US_BASE = "https://api.binance.us"
BYBIT_BASE = "https://api.bybit.com"
OKX_BASE = "https://www.okx.com"
FEAR_GREED_URL = "https://api.alternative.me/fng/"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Skip a provider this long after a network failure (geo-block / rate limit).
_down_until: dict[str, float] = {}

# module-level cache: key -> (expires_ts, value)
_cache: dict[str, tuple[float, Any]] = {}


def _cached(key: str, ttl: int = CACHE_TTL) -> Any:
    item = _cache.get(key)
    if item and item[0] > time.time():
        return item[1]
    return None


def _store(key: str, value: Any, ttl: int = CACHE_TTL) -> Any:
    _cache[key] = (time.time() + ttl, value)
    return value


def _up(name: str) -> bool:
    return time.time() >= _down_until.get(name, 0.0)


def _mark_down(name: str) -> None:
    _down_until[name] = time.time() + COOLDOWN


def _get(url: str, *, provider: str, params: dict | None = None) -> Any:
    """GET with cooldown bookkeeping. Raises on failure (caller handles)."""
    if not _up(provider):
        raise RuntimeError(f"{provider} in cooldown")
    try:
        r = requests.get(url, params=params or {}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        _mark_down(provider)
        raise


def _base_quote(symbol: str) -> tuple[str, str]:
    s = symbol.upper().replace("-", "/").replace("_", "/")
    if "/" in s:
        base, quote = s.split("/", 1)
        return base, quote
    for q in ("USDT", "USDC", "USD"):
        if s.endswith(q):
            return s[: -len(q)], q
    return s, "USD"


def to_pair(symbol: str) -> str:
    """BTC/USD -> BTCUSDT."""
    base, _ = _base_quote(symbol)
    return f"{base}USDT"


# ---------------------------------------------------------------------------
# Order-book imbalance (Binance.US -> Coinbase)
# ---------------------------------------------------------------------------
def orderbook_imbalance(symbol: str) -> dict[str, Any] | None:
    """Top-of-book bid/ask imbalance in [-1, 1]. +1 = all bids, -1 = all asks.

    Not a depth-weighted microprice; a cheap, keyless proxy for short-horizon
    order-flow pressure. None when no provider is reachable.
    """
    key = f"ob:{to_pair(symbol)}"
    hit = _cached(key, ttl=300)
    if hit is not None:
        return hit

    attempts = (
        ("binance_us", f"{BINANCE_US_BASE}/api/v3/depth", {"symbol": to_pair(symbol), "limit": 50}),
        ("coinbase", f"https://api.exchange.coinbase.com/products/{_base_quote(symbol)[0]}-USD/book", {"level": 1}),
    )
    for provider, url, params in attempts:
        try:
            data = _get(url, provider=provider, params=params)
        except Exception as e:
            logger.debug("orderbook %s failed: %s", provider, str(e)[:120])
            continue
        try:
            bids = data.get("bids") or []
            asks = data.get("asks") or []
            bid_v = sum(float(x[1]) for x in bids[:5])
            ask_v = sum(float(x[1]) for x in asks[:5])
            total = bid_v + ask_v
            if total <= 0:
                continue
            imb = (bid_v - ask_v) / total
            out = _store(key, {
                "imbalance": round(imb, 4),
                "bid_volume": round(bid_v, 4),
                "ask_volume": round(ask_v, 4),
                "source": provider,
            }, ttl=300)
            return out
        except Exception as e:
            logger.debug("orderbook parse %s failed: %s", provider, str(e)[:120])
            continue
    return None


# ---------------------------------------------------------------------------
# Funding rate / open interest (Bybit -> OKX)
# ---------------------------------------------------------------------------
def funding_oi(symbol: str) -> dict[str, Any] | None:
    """Funding rate + open interest. None when unavailable (geo-block likely)."""
    key = f"fo:{to_pair(symbol)}"
    hit = _cached(key, ttl=600)
    if hit is not None:
        return hit

    pair = to_pair(symbol)

    # Bybit linear perp funding + OI
    try:
        fr = _get(f"{BYBIT_BASE}/v5/market/funding/history", provider="bybit",
                  params={"category": "linear", "symbol": pair, "limit": 1})
        oi = _get(f"{BYBIT_BASE}/v5/market/tickers", provider="bybit",
                  params={"category": "linear", "symbol": pair})
        funding = (fr.get("result") or {}).get("list") or []
        tickers = (oi.get("result") or {}).get("list") or []
        if funding and tickers:
            out = _store(key, {
                "funding_rate": float(funding[0].get("fundingRate", 0.0)),
                "open_interest": float(tickers[0].get("openInterest", 0.0) or 0.0),
                "source": "bybit",
            }, ttl=600)
            return out
    except Exception as e:
        logger.debug("bybit funding failed: %s", str(e)[:120])

    # OKX fallback
    try:
        inst = pair  # OKX uses e.g. BTC-USDT-SWAP for perps; probe with spot first
        oi_okx = _get(f"{OKX_BASE}/api/v5/market/ticker", provider="okx",
                      params={"instId": inst})
        tick = (oi_okx.get("data") or [{}])[0]
        fr_okx = _get(f"{OKX_BASE}/api/v5/public/funding-rate", provider="okx",
                      params={"instId": inst})
        fnd = (fr_okx.get("data") or [{}])[0]
        if tick:
            out = _store(key, {
                "funding_rate": float(fnd.get("fundingRate") or 0.0),
                "open_interest": float(tick.get("volCcy24h") or 0.0),
                "source": "okx",
            }, ttl=600)
            return out
    except Exception as e:
        logger.debug("okx funding failed: %s", str(e)[:120])

    return None


# ---------------------------------------------------------------------------
# Fear & Greed (alternative.me)
# ---------------------------------------------------------------------------
def fear_greed() -> dict[str, Any] | None:
    """Market-wide Fear & Greed index 0..100. None on failure."""
    hit = _cached("fng", ttl=1800)
    if hit is not None:
        return hit
    try:
        data = _get(FEAR_GREED_URL, provider="alternative_me", params={"limit": 2})
        rows = data.get("data") or []
        if not rows:
            return None
        cur = rows[0]
        prev = rows[1] if len(rows) > 1 else None
        out = _store("fng", {
            "value": int(cur.get("value", 0)),
            "classification": cur.get("value_classification", ""),
            "prev_value": int(prev.get("value", 0)) if prev else None,
            "source": "alternative.me",
        }, ttl=1800)
        return out
    except Exception as e:
        logger.debug("fear&greed failed: %s", str(e)[:120])
        return None


# ---------------------------------------------------------------------------
# BTC dominance (CoinGecko)
# ---------------------------------------------------------------------------
def btc_dominance() -> dict[str, Any] | None:
    """BTC market-cap dominance %. None on failure (rate-limited often)."""
    hit = _cached("btc_dom", ttl=3600)
    if hit is not None:
        return hit
    try:
        data = _get(f"{COINGECKO_BASE}/global", provider="coingecko")
        m = (data.get("data") or {})
        dom = m.get("market_cap_percentage") or {}
        btc = dom.get("btc")
        if btc is None:
            return None
        out = _store("btc_dom", {
            "btc_dominance": round(float(btc), 2),
            "total_market_cap_usd": m.get("total_market_cap", {}).get("usd"),
            "source": "coingecko",
        }, ttl=3600)
        return out
    except Exception as e:
        logger.debug("btc dominance failed: %s", str(e)[:120])
        return None


# ---------------------------------------------------------------------------
# Aggregation + confidence modifier
# ---------------------------------------------------------------------------
# Confirmation/dampening bands applied to a signal's confidence.
#   sentiment confirm  -> small boost (+ up to 0.05)
#   sentiment oppose   -> small damp ( - up to 0.05)
#   crowded/extreme    -> extra caution tag, no extra boost
MAX_ADJUST = 0.05


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def sentiment_for(symbol: str, direction: str) -> dict[str, Any]:
    """Aggregate sentiment for a symbol and compute a confidence modifier.

    Returns dict with: available, modifier (float), tag (str|None), feeds (dict).
    Crypto-only; callers on other markets get a no-op result.
    """
    feeds: dict[str, Any] = {}
    ob = orderbook_imbalance(symbol)
    if ob:
        feeds["orderflow"] = ob
    fo = funding_oi(symbol)
    if fo:
        feeds["derivatives"] = fo
    fg = fear_greed()
    if fg:
        feeds["fear_greed"] = fg
    bd = btc_dominance()
    if bd:
        feeds["btc_dominance"] = bd

    if not feeds:
        return {"available": False, "modifier": 0.0, "tag": None, "feeds": {}}

    modifier = 0.0
    tags: list[str] = []
    long_side = direction == "BUY"

    # Order-flow: positive imbalance supports BUY, negative supports SELL.
    ob_imb = (feeds.get("orderflow") or {}).get("imbalance")
    if ob_imb is not None:
        support = ob_imb if long_side else -ob_imb  # >0 = confirms
        modifier += _clamp(support * 0.03, -MAX_ADJUST, MAX_ADJUST)
        if support < -0.35:
            tags.append("orderflow_against")

    # Funding: extreme positive funding = crowded longs (caution on BUY).
    funding = (feeds.get("derivatives") or {}).get("funding_rate")
    if funding is not None:
        if long_side and funding > 0.0005:
            modifier -= MAX_ADJUST * 0.5
            tags.append("crowded_longs")
        elif (not long_side) and funding < -0.0005:
            modifier -= MAX_ADJUST * 0.5
            tags.append("crowded_shorts")
        elif long_side and funding < 0:
            modifier += MAX_ADJUST * 0.4
            tags.append("shorts_paying")
        elif (not long_side) and funding > 0:
            modifier += MAX_ADJUST * 0.4
            tags.append("longs_paying")

    # Fear & Greed: extreme greed on a BUY is contrarian caution.
    fng_v = (feeds.get("fear_greed") or {}).get("value")
    if fng_v is not None:
        if long_side and fng_v >= 75:
            modifier -= MAX_ADJUST * 0.4
            tags.append("extreme_greed")
        elif (not long_side) and fng_v <= 25:
            modifier -= MAX_ADJUST * 0.4
            tags.append("extreme_fear")
        elif (long_side and fng_v <= 30) or ((not long_side) and fng_v >= 70):
            modifier += MAX_ADJUST * 0.3
            tags.append("contrarian")

    # BTC dominance rising = risk-off for alts (only matters for non-BTC).
    base, _ = _base_quote(symbol)
    dom = (feeds.get("btc_dominance") or {}).get("btc_dominance")
    if dom is not None and base != "BTC" and long_side and dom > 55:
        modifier -= MAX_ADJUST * 0.2
        tags.append("risk_off_alts")

    modifier = round(_clamp(modifier, -MAX_ADJUST, MAX_ADJUST), 4)
    tag = "+".join(tags) if tags else None
    return {"available": True, "modifier": modifier, "tag": tag, "feeds": feeds}


def probe(symbol: str = "BTC/USD") -> list[dict[str, Any]]:
    """Diagnostic: test every sentiment feed from this host. Never raises."""
    checks = (
        ("orderflow", lambda: orderbook_imbalance(symbol)),
        ("derivatives", lambda: funding_oi(symbol)),
        ("fear_greed", fear_greed),
        ("btc_dominance", btc_dominance),
    )
    out: list[dict[str, Any]] = []
    for name, fn in checks:
        t = time.time()
        try:
            val = fn()
            out.append({
                "feed": name,
                "ok": val is not None,
                "value": val,
                "latency_ms": int((time.time() - t) * 1000),
            })
        except Exception as e:
            out.append({"feed": name, "ok": False, "error": str(e)[:120],
                        "latency_ms": int((time.time() - t) * 1000)})
    return out
