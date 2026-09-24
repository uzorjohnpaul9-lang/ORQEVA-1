"""
Rate Limiter - Protects all external API calls.
Usage: @rate_limit(calls=10, period=60) on any function.
"""
import time
import threading
from functools import wraps
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe rate limiter using sliding window."""

    def __init__(self):
        self._windows: Dict[str, list] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str, max_calls: int, period: float) -> bool:
        now = time.time()
        with self._lock:
            if key not in self._windows:
                self._windows[key] = []
            window = self._windows[key]
            window[:] = [t for t in window if now - t < period]
            if len(window) < max_calls:
                window.append(now)
                return True
            return False

    def wait_time(self, key: str, max_calls: int, period: float) -> float:
        now = time.time()
        with self._lock:
            window = self._windows.get(key, [])
            if len(window) >= max_calls:
                return period - (now - window[0])
            return 0.0


_limiter = RateLimiter()


def rate_limit(calls: int = 10, period: float = 60.0):
    """Decorator to rate-limit function calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__module__}.{func.__qualname__}"
            if not _limiter.is_allowed(key, calls, period):
                wait = _limiter.wait_time(key, calls, period)
                logger.warning(f"Rate limited: {key} - waiting {wait:.1f}s")
                time.sleep(wait)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Pre-configured limiters for external APIs
def telegram_limit(func):
    """Max 30 messages/second per bot (Telegram limit)."""
    return rate_limit(calls=28, period=1.0)(func)


def api_limit(func):
    """Max 60 calls/minute for market data APIs."""
    return rate_limit(calls=55, period=60.0)(func)


def broker_limit(func):
    """Max 10 orders/minute to prevent runaway trading."""
    return rate_limit(calls=10, period=60.0)(func)
