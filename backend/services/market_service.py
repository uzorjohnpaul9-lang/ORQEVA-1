"""
Market Data Service - Phase 6: Live Market Data.

Live quotes and chart bars for the dashboard:
- Stocks (indices via ETF proxies, movers): Alpaca
- Forex / Crypto / Gold: Twelve Data REST API

Credit budget (Twelve Data free tier = 8 credits/min, 800/day):
All responses go through the shared TTL cache so repeated dashboard
refreshes cost zero credits until the TTL expires.
"""
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

from backend.middleware.cache import cache

logger = logging.getLogger(__name__)

TWELVE_DATA_BASE = "https://api.twelvedata.com"
QUOTE_TTL = 60      # seconds - live quotes
BARS_TTL = 300      # seconds - chart series

# Overview cards: (label, market, symbol)
OVERVIEW_SYMBOLS = [
    {"label": "S&P 500", "market": "stock", "symbol": "SPY"},
    {"label": "NASDAQ 100", "market": "stock", "symbol": "QQQ"},
    {"label": "DOW 30", "market": "stock", "symbol": "DIA"},
    {"label": "Bitcoin", "market": "crypto", "symbol": "BTC/USD"},
    {"label": "Ethereum", "market": "crypto", "symbol": "ETH/USD"},
    {"label": "EUR/USD", "market": "forex", "symbol": "EUR/USD"},
    {"label": "Gold", "market": "commodity", "symbol": "XAU/USD"},
]

# Stock universe for top movers (mirrors stock engine symbols)
MOVER_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "TSLA", "META", "JPM", "V", "UNH",
    "XOM", "JNJ", "WMT", "PG", "MA",
    "HD", "CVX", "MRK", "ABBV", "LLY",
]


def _td_api_key() -> str:
    return os.getenv("TWELVE_DATA_API_KEY", "")


def _alpaca_data_client():
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        api_key = os.getenv("ALPACA_API_KEY", "")
        secret = os.getenv("ALPACA_SECRET_KEY", "")
        if api_key and secret:
            return StockHistoricalDataClient(api_key, secret)
    except Exception as e:
        logger.warning(f"Alpaca data client unavailable: {e}")
    return None


def _td_quote(symbol: str) -> dict[str, Any] | None:
    """Fetch one quote from Twelve Data. Returns None on failure."""
    key = _td_api_key()
    if not key:
        return None
    try:
        r = requests.get(
            f"{TWELVE_DATA_BASE}/quote",
            params={"symbol": symbol, "apikey": key},
            timeout=15,
        )
        data = r.json()
        # Twelve Data returns {"code": xxx, "message": "..."} on errors
        if "close" not in data:
            logger.warning(f"Twelve Data quote failed for {symbol}: {data.get('message')}")
            return None
        close = float(data["close"])
        prev = float(data.get("previous_close") or close)
        change = float(data.get("change") or (close - prev))
        pct = float(data.get("percent_change") or ((change / prev * 100) if prev else 0))
        return {
            "symbol": symbol,
            "price": round(close, 6),
            "previous_close": round(prev, 6),
            "change": round(change, 6),
            "change_percent": round(pct, 4),
            "open": float(data.get("open") or 0),
            "high": float(data.get("high") or 0),
            "low": float(data.get("low") or 0),
            "is_market_open": bool(data.get("is_market_open", False)),
            "source": "twelvedata",
        }
    except Exception as e:
        logger.error(f"Twelve Data quote error for {symbol}: {e}")
        return None


def _alpaca_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Batch latest trades + daily change for stocks via Alpaca snapshots."""
    out: dict[str, dict[str, Any]] = {}
    client = _alpaca_data_client()
    if client is None or not symbols:
        return out
    try:
        from alpaca.data.requests import StockSnapshotRequest
        req = StockSnapshotRequest(symbol_or_symbols=symbols)
        snaps = client.get_stock_snapshot(req)
        items = snaps.items() if hasattr(snaps, "items") else []
        for sym, s in items:
            try:
                price = float(s.latest_trade.price) if s.latest_trade else None
                prev_close = float(s.previous_daily_bar.close) if s.previous_daily_bar else None
                daily_bar = s.daily_bar
                day_close = float(daily_bar.close) if daily_bar else price
                if price is None or prev_close in (None, 0):
                    continue
                change = price - prev_close
                out[sym] = {
                    "symbol": sym,
                    "price": round(price, 4),
                    "previous_close": round(prev_close, 4),
                    "change": round(change, 4),
                    "change_percent": round(change / prev_close * 100, 4),
                    "day_high": float(daily_bar.high) if daily_bar else None,
                    "day_low": float(daily_bar.low) if daily_bar else None,
                    "is_market_open": None,
                    "source": "alpaca",
                }
            except (TypeError, AttributeError, ValueError):
                continue
    except Exception as e:
        logger.error(f"Alpaca snapshot error: {e}")
    return out


def get_quote(market: str, symbol: str) -> dict[str, Any]:
    """Single quote with cache. market: stock|forex|crypto|commodity."""
    cache_key = f"mkt:quote:{market}:{symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result: dict[str, Any]
    if market == "stock":
        quotes = _alpaca_quotes([symbol])
        if symbol in quotes:
            result = quotes[symbol]
        else:
            result = {"symbol": symbol, "error": "quote_unavailable"}
    else:
        q = _td_quote(symbol)
        result = q if q else {"symbol": symbol, "error": "quote_unavailable"}

    cache.set(cache_key, result, ttl=QUOTE_TTL)
    return result


def get_overview() -> dict[str, Any]:
    """Index/commodity/crypto cards + stock top movers."""
    cache_key = "mkt:overview"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    indices: list[dict[str, Any]] = []
    td_symbols: list[dict[str, str]] = []
    alpaca_symbols: list[str] = []

    for item in OVERVIEW_SYMBOLS:
        if item["market"] == "stock":
            alpaca_symbols.append(item["symbol"])
        else:
            td_symbols.append(item)

    stock_quotes = _alpaca_quotes(alpaca_symbols)
    with ThreadPoolExecutor(max_workers=4) as pool:
        td_results = list(pool.map(lambda item: _td_quote(item["symbol"]), td_symbols))
    td_by_symbol = {item["symbol"]: q for item, q in zip(td_symbols, td_results)}
    for item in OVERVIEW_SYMBOLS:
        label, market, symbol = item["label"], item["market"], item["symbol"]
        if market == "stock":
            q = stock_quotes.get(symbol)
        else:
            q = td_by_symbol.get(symbol)
        if q and "error" not in q:
            indices.append({
                "label": label,
                "market": market,
                "symbol": symbol,
                "price": q["price"],
                "change": q["change"],
                "change_percent": q["change_percent"],
                "is_market_open": q.get("is_market_open"),
            })
        else:
            indices.append({
                "label": label, "market": market, "symbol": symbol,
                "price": None, "change": None, "change_percent": None,
                "is_market_open": None,
            })

    movers = get_movers(use_cache=False)

    result = {"indices": indices, "movers": movers}
    cache.set(cache_key, result, ttl=QUOTE_TTL)
    return result


def get_movers(use_cache: bool = True) -> list[dict[str, Any]]:
    """Top 5 gainers + losers across the stock watchlist."""
    cache_key = "mkt:movers"
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    quotes = _alpaca_quotes(MOVER_SYMBOLS)
    ranked = sorted(quotes.values(), key=lambda q: q["change_percent"])
    losers = [m for m in ranked[:5] if m["change_percent"] < 0]
    gainers = [m for m in ranked[-5:] if m["change_percent"] > 0]
    gainers.reverse()
    result = {"gainers": gainers, "losers": losers}
    cache.set(cache_key, result, ttl=QUOTE_TTL)
    return result


def get_bars(market: str, symbol: str, interval: str = "1day", outputsize: int = 30) -> dict[str, Any]:
    """OHLC series for charts. Cached longer than quotes."""
    cache_key = f"mkt:bars:{market}:{symbol}:{interval}:{outputsize}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result: dict[str, Any]
    if market == "stock":
        result = _alpaca_bars(symbol, interval, outputsize)
    else:
        result = _td_bars(symbol, interval, outputsize)

    if "bars" in result:
        cache.set(cache_key, result, ttl=BARS_TTL)
    return result


def _td_bars(symbol: str, interval: str, outputsize: int) -> dict[str, Any]:
    key = _td_api_key()
    if not key:
        return {"error": "no_api_key"}
    valid = {"1min", "5min", "15min", "30min", "1h", "2h", "4h", "1day", "1week"}
    if interval not in valid:
        interval = "1day"
    try:
        r = requests.get(
            f"{TWELVE_DATA_BASE}/time_series",
            params={
                "symbol": symbol,
                "interval": interval,
                "outputsize": min(outputsize, 200),
                "apikey": key,
            },
            timeout=15,
        )
        data = r.json()
        if "values" not in data:
            return {"error": data.get("message", "bars_unavailable")}
        bars = [
            {
                "time": v["datetime"],
                "open": float(v["open"]),
                "high": float(v["high"]),
                "low": float(v["low"]),
                "close": float(v["close"]),
            }
            for v in reversed(data["values"])
        ]
        return {"symbol": symbol, "interval": interval, "bars": bars}
    except Exception as e:
        logger.error(f"Twelve Data bars error for {symbol}: {e}")
        return {"error": "bars_unavailable"}


def _alpaca_bars(symbol: str, interval: str, outputsize: int) -> dict[str, Any]:
    client = _alpaca_data_client()
    if client is None:
        return {"error": "no_api_key"}
    tf_map = {
        "5min": ("Minute", 5), "15min": ("Minute", 15), "30min": ("Minute", 30),
        "1h": ("Hour", 1), "1day": ("Day", 1),
    }
    unit_name, amount = tf_map.get(interval, ("Day", 1))
    days_back = max(2, min(outputsize, 200))  # calendar days of history to request
    try:
        from datetime import datetime, timedelta
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        tf = TimeFrame(amount, TimeFrameUnit[unit_name])
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=datetime.utcnow() - timedelta(days=days_back + 5),
            limit=min(outputsize, 200),
        )
        resp = client.get_stock_bars(req)
        df = resp.df
        if df is None or len(df) == 0:
            return {"error": "bars_unavailable"}
        df = df.reset_index()
        bars = []
        for _, row in df.iterrows():
            ts = row["timestamp"]
            bars.append({
                "time": ts.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })
        return {"symbol": symbol, "interval": interval, "bars": bars}
    except Exception as e:
        logger.error(f"Alpaca bars error for {symbol}: {e}")
        return {"error": "bars_unavailable"}


def get_discovery(top_n: int = 10) -> dict[str, Any]:
    """Crypto discovery results (cached scan results only - no fresh scan)."""
    cache_key = f"mkt:discovery:{top_n}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    coins: list[dict[str, Any]] = []
    try:
        import sys
        from pathlib import Path
        root = str(Path(__file__).parent.parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from engines.crypto_discovery import CryptoDiscovery
        d = CryptoDiscovery()
        results = d._get_cached_results(top_n)
        for c in results:
            coins.append({
                "symbol": c.symbol,
                "price": round(c.price, 6),
                "rsi": round(c.rsi, 1),
                "score": round(c.score, 3),
                "momentum_5d": round(c.momentum_5d, 4),
                "direction": c.direction,
            })
    except Exception as e:
        logger.error(f"Crypto discovery error: {e}")

    result = {"coins": coins, "cached_scan": True}
    cache.set(cache_key, result, ttl=BARS_TTL)
    return result
