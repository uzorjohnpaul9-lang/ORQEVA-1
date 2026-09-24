import time
from collections import defaultdict
from fastapi import Request, HTTPException


class RateLimiter:
    """Per-user rate limiter based on tier."""

    LIMITS = {
        "free": {"requests": 30, "window": 60},
        "premium": {"requests": 120, "window": 60},
        "vip": {"requests": 300, "window": 60},
        "admin": {"requests": 1000, "window": 60},
    }

    def __init__(self):
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str, tier: str = "free") -> bool:
        now = time.time()
        limit = self.LIMITS.get(tier, self.LIMITS["free"])
        window = limit["window"]
        max_req = limit["requests"]

        self._hits[user_id] = [t for t in self._hits[user_id] if now - t < window]
        if len(self._hits[user_id]) >= max_req:
            return False
        self._hits[user_id].append(now)
        return True

    def remaining(self, user_id: str, tier: str = "free") -> int:
        now = time.time()
        limit = self.LIMITS.get(tier, self.LIMITS["free"])
        window = limit["window"]
        recent = [t for t in self._hits[user_id] if now - t < window]
        return max(0, limit["requests"] - len(recent))


rate_limiter = RateLimiter()


def check_rate_limit(user_id: str, tier: str = "free"):
    if not rate_limiter.check(user_id, tier):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for {tier} tier. Try again later."
        )
