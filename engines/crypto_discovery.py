"""
Crypto Discovery — scans a wider universe of coins and ranks by momentum.
Finds "potential new coins coming up" beyond the fixed watchlist.
Uses Twelve Data API with rate limiting and caching.
"""
import os
import time
import json
import logging
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── Universe: top 50 coins by relevance + trending alts ──────────────
CRYPTO_UNIVERSE = [
    # Tier 1 — Blue chips
    "BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD", "XRP/USD",
    "ADA/USD", "DOGE/USD", "AVAX/USD", "DOT/USD", "LINK/USD",
    "MATIC/USD", "UNI/USD", "ATOM/USD", "FIL/USD", "LTC/USD",
    # Tier 2 — High momentum alts
    "APT/USD", "ARB/USD", "OP/USD", "NEAR/USD", "INJ/USD",
    "TIA/USD", "SUI/USD", "SEI/USD", "PEPE/USD", "WIF/USD",
    # Tier 3 — AI / RWA / Meme hot sectors
    "FET/USD", "RENDER/USD", "ONDO/USD", "TRUMP/USD", "FARTCOIN/USD",
    # Tier 4 — Micro-caps with momentum potential
    "BONK/USD", "FLOKI/USD", "SHIB/USD", "ORDI/USD", "STX/USD",
    "IMX/USD", "AAVE/USD", "MKR/USD", "CRV/USD", "LDO/USD",
    "GRT/USD", "SAND/USD", "MANA/USD", "AXS/USD", "ENJ/USD",
    "RUNE/USD", "FTM/USD", "KAS/USD", "HBAR/USD", "VET/USD",
]

# Rate: 8 credits/min on free tier, 800/day
RATE_LIMIT_PER_MIN = 8
RATE_LIMIT_PER_DAY = 800
DAILY_SCAN_BUDGET = 50  # Use max 50 calls per full scan
SCAN_COOLDOWN_SECONDS = 900  # 15 minutes between full scans


class CoinMomentum:
    """Stores momentum data for a single coin."""
    __slots__ = (
        "symbol", "price", "rsi", "macd_hist", "bb_position",
        "momentum_5d", "momentum_10d", "volume_trend",
        "score", "direction", "reasons",
    )

    def __init__(self, symbol: str, price: float = 0, rsi: float = 50,
                 macd_hist: float = 0, bb_position: float = 0.5,
                 momentum_5d: float = 0, momentum_10d: float = 0,
                 volume_trend: float = 0, score: float = 0,
                 direction: str = "", reasons: Optional[List[str]] = None):
        self.symbol = symbol
        self.price = price
        self.rsi = rsi
        self.macd_hist = macd_hist
        self.bb_position = bb_position
        self.momentum_5d = momentum_5d
        self.momentum_10d = momentum_10d
        self.volume_trend = volume_trend
        self.score = score
        self.direction = direction
        self.reasons = reasons or []


class CryptoDiscovery:
    """
    Scans a wider crypto universe and ranks coins by momentum.
    Designed for VIP channel — shows which coins are "coming up."
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self._api_key = os.getenv("TWELVE_DATA_API_KEY", "")
        self._base_url = "https://api.twelvedata.com"
        self._cache_dir = cache_dir or os.path.join(
            os.path.dirname(__file__), "..", "data"
        )
        self._cache_file = os.path.join(self._cache_dir, "discovery_cache.json")
        self._last_scan: Optional[datetime] = None
        self._daily_calls = 0
        self._daily_reset: Optional[datetime] = None
        self._load_cache()

    def _load_cache(self):
        """Load cached scan results."""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, "r") as f:
                    cache = json.load(f)
                self._last_scan = datetime.fromisoformat(cache.get("last_scan", ""))
                self._daily_calls = cache.get("daily_calls", 0)
                self._daily_reset = datetime.fromisoformat(cache["daily_reset"]) if cache.get("daily_reset") else None
        except Exception:
            self._last_scan = None
            self._daily_calls = 0
            self._daily_reset = None

    def _save_cache(self):
        """Persist scan state."""
        try:
            os.makedirs(self._cache_dir, exist_ok=True)
            with open(self._cache_file, "w") as f:
                json.dump({
                    "last_scan": self._last_scan.isoformat() if self._last_scan else "",
                    "daily_calls": self._daily_calls,
                    "daily_reset": self._daily_reset.isoformat() if self._daily_reset else "",
                }, f)
        except Exception as e:
            logger.error(f"Failed to save discovery cache: {e}")

    def _reset_daily_if_needed(self):
        """Reset daily call counter at midnight."""
        now = datetime.now()
        if self._daily_reset is None or now.date() > self._daily_reset.date():
            self._daily_calls = 0
            self._daily_reset = now

    def _can_scan(self) -> Tuple[bool, str]:
        """Check if we can afford another full scan."""
        self._reset_daily_if_needed()

        if self._daily_calls >= RATE_LIMIT_PER_DAY:
            return False, f"Daily API limit reached ({self._daily_calls}/{RATE_LIMIT_PER_DAY})"

        remaining = RATE_LIMIT_PER_DAY - self._daily_calls
        needed = min(DAILY_SCAN_BUDGET, len(CRYPTO_UNIVERSE))
        if remaining < needed:
            return False, f"Not enough API credits ({remaining} remaining, need {needed})"

        if self._last_scan:
            elapsed = (datetime.now() - self._last_scan).total_seconds()
            if elapsed < SCAN_COOLDOWN_SECONDS:
                wait = int(SCAN_COOLDOWN_SECONDS - elapsed)
                return False, f"Scan cooldown — wait {wait}s"

        return True, "OK"

    def _fetch_batch(self, symbols: List[str], lookback: int = 30) -> Dict[str, List[float]]:
        """Fetch prices for multiple symbols in one API call."""
        if not symbols or not self._api_key:
            return {}

        batch_str = ",".join(symbols)
        try:
            r = requests.get(f"{self._base_url}/time_series", params={
                "symbol": batch_str,
                "interval": "1day",
                "outputsize": lookback,
                "apikey": self._api_key,
            }, timeout=20)
            self._daily_calls += 1
            self._save_cache()

            data = r.json()
            result = {}
            for sym in symbols:
                sym_data = data.get(sym, {})
                if isinstance(sym_data, dict) and "values" in sym_data:
                    prices = [float(v["close"]) for v in reversed(sym_data["values"])]
                    if prices:
                        result[sym] = prices
            return result
        except Exception as e:
            logger.error(f"Discovery batch fetch failed: {e}")
            return {}

    def _score_coin(self, symbol: str, prices: List[float]) -> Optional[CoinMomentum]:
        """Score a single coin based on momentum indicators."""
        if len(prices) < 26:
            return None

        from engines.indicators import calculate_rsi, calculate_macd, calculate_bollinger

        current = prices[-1]
        rsi = calculate_rsi(prices)
        macd = calculate_macd(prices)
        bb = calculate_bollinger(prices)

        # RSI position (0 = oversold, 1 = overbought)
        rsi_norm = rsi / 100.0

        # Bollinger position (0 = at lower, 1 = at upper)
        bb_range = bb["upper"] - bb["lower"]
        bb_position = (current - bb["lower"]) / bb_range if bb_range > 0 else 0.5

        # 5-day and 10-day momentum
        mom_5d = (prices[-1] / prices[-6] - 1) * 100 if len(prices) >= 6 else 0
        mom_10d = (prices[-1] / prices[-11] - 1) * 100 if len(prices) >= 11 else 0

        # Composite score: momentum-heavy for discovery
        score = 0.0
        reasons = []

        # Strong momentum (most important for discovery)
        if mom_5d > 5:
            score += 0.20
            reasons.append(f"+{mom_5d:.1f}% 5d momentum")
        elif mom_5d > 15:
            score += 0.25
            reasons.append(f"Strong +{mom_5d:.1f}% 5d momentum")
        elif mom_5d < -10:
            score += 0.15  # Oversold bounce potential
            reasons.append(f"Momentum bottom {mom_5d:.1f}%")

        if mom_10d > 10:
            score += 0.15
            reasons.append(f"+{mom_10d:.1f}% 10d momentum")
        elif mom_10d < -15:
            score += 0.10
            reasons.append(f"Deep pullback {mom_10d:.1f}%")

        # RSI signals
        if rsi < 30:
            score += 0.25
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi < 40:
            score += 0.10
            reasons.append(f"RSI low ({rsi:.0f})")
        elif rsi > 80:
            score += 0.20
            reasons.append(f"RSI extreme overbought ({rsi:.0f})")

        # MACD
        if macd["histogram"] > 0 and macd["macd"] > macd["signal"]:
            score += 0.15
            reasons.append("MACD bullish crossover")
        elif macd["histogram"] < 0 and mom_5d > 0:
            score += 0.10
            reasons.append("MACD divergence (bullish)")

        # Bollinger squeeze/expansion
        if bb_position < 0.1:
            score += 0.15
            reasons.append("Near lower Bollinger (bounce zone)")
        elif bb_position > 0.9:
            score += 0.10
            reasons.append("Near upper Bollinger (breakout)")

        # Determine direction
        if score >= 0.30:
            if rsi < 40 or mom_5d > 0 or bb_position < 0.3:
                direction = "BUY"
            else:
                direction = "WATCH"
        else:
            direction = ""

        return CoinMomentum(
            symbol=symbol, price=current, rsi=rsi,
            macd_hist=macd["histogram"], bb_position=bb_position,
            momentum_5d=mom_5d, momentum_10d=mom_10d,
            score=score, direction=direction, reasons=reasons,
        )

    def run_discovery(self, top_n: int = 10) -> List[CoinMomentum]:
        """
        Full discovery scan. Returns top N coins ranked by momentum.
        Rate-limited and cached to stay within API budget.
        """
        can, reason = self._can_scan()
        if not can:
            logger.info(f"Discovery scan skipped: {reason}")
            return self._get_cached_results(top_n)

        logger.info(f"Running crypto discovery scan ({len(CRYPTO_UNIVERSE)} coins)...")
        start = time.time()

        # Batch into groups of 8 (rate limit)
        all_coins: List[CoinMomentum] = []
        batch_size = RATE_LIMIT_PER_MIN
        batches = [
            CRYPTO_UNIVERSE[i:i + batch_size]
            for i in range(0, len(CRYPTO_UNIVERSE), batch_size)
        ]

        for batch in batches:
            if self._daily_calls >= DAILY_SCAN_BUDGET:
                logger.info(f"Discovery budget exhausted ({self._daily_calls}/{DAILY_SCAN_BUDGET})")
                break

            prices_map = self._fetch_batch(batch, lookback=30)
            for sym, prices in prices_map.items():
                coin = self._score_coin(sym, prices)
                if coin and coin.score > 0:
                    all_coins.append(coin)

            # Respect rate limit: 1 second between batches
            time.sleep(1.5)

        # Sort by score descending
        all_coins.sort(key=lambda c: c.score, reverse=True)

        elapsed = time.time() - start
        logger.info(
            f"Discovery complete: {len(all_coins)} coins scored in {elapsed:.1f}s "
            f"(API calls: {self._daily_calls}/{RATE_LIMIT_PER_DAY} today)"
        )

        # Cache results
        self._last_scan = datetime.now()
        self._save_cache()
        self._cache_results(all_coins)

        return all_coins[:top_n]

    def _cache_results(self, coins: List[CoinMomentum]):
        """Cache scored coins for when we can't re-scan."""
        try:
            cache_path = os.path.join(self._cache_dir, "discovery_results.json")
            data = []
            for c in coins:
                data.append({
                    "symbol": c.symbol,
                    "price": c.price,
                    "rsi": c.rsi,
                    "macd_hist": c.macd_hist,
                    "bb_position": c.bb_position,
                    "momentum_5d": c.momentum_5d,
                    "momentum_10d": c.momentum_10d,
                    "score": c.score,
                    "direction": c.direction,
                    "reasons": c.reasons,
                    "timestamp": datetime.now().isoformat(),
                })
            with open(cache_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to cache discovery results: {e}")

    def _get_cached_results(self, top_n: int) -> List[CoinMomentum]:
        """Return cached results when scan is on cooldown."""
        try:
            cache_path = os.path.join(self._cache_dir, "discovery_results.json")
            if os.path.exists(cache_path):
                with open(cache_path) as f:
                    data = json.load(f)
                coins = []
                for item in data[:top_n]:
                    coins.append(CoinMomentum(
                        symbol=item["symbol"],
                        price=item["price"],
                        rsi=item["rsi"],
                        macd_hist=item["macd_hist"],
                        bb_position=item["bb_position"],
                        momentum_5d=item["momentum_5d"],
                        momentum_10d=item["momentum_10d"],
                        score=item["score"],
                        direction=item["direction"],
                        reasons=item["reasons"],
                    ))
                return coins
        except Exception:
            pass
        return []
