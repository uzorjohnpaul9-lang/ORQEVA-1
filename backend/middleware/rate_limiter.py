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


# Unauthenticated endpoints key off the caller's IP instead of a user id.
_public_hits: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    return request.client.host if request.client else "unknown"


def check_public_rate_limit(request: Request, *, bucket: str = "public",
                            limit: int = 60, window: int = 60) -> None:
    """Per-IP limiter for endpoints that have no authenticated user."""
    now = time.time()
    key = f"{bucket}:{_client_ip(request)}"
    hits = _public_hits[key]
    hits[:] = [t for t in hits if now - t < window]
    if len(hits) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try again shortly.",
            headers={"Retry-After": str(window)},
        )
    hits.append(now)
