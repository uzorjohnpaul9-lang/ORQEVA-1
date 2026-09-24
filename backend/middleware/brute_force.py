"""In-memory brute-force lockout for login (Phase 16).

Per (email, ip) bucket: 5 failures -> 15 min lockout. Single-process only;
fine for the SQLite single-node deployment, swap for Redis when scaling out.
"""
import time
from collections import defaultdict

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

_failures: dict[str, list[float]] = defaultdict(list)


def _key(email: str, ip: str) -> str:
    return f"{email.strip().lower()}|{ip}"


def is_locked(email: str, ip: str) -> int:
    """Returns seconds remaining on lockout, or 0."""
    k = _key(email, ip)
    now = time.time()
    recent = [t for t in _failures[k] if now - t < WINDOW_SECONDS]
    if len(recent) >= MAX_FAILURES:
        return int(WINDOW_SECONDS - (now - recent[0])) + 1
    return 0


def record_failure(email: str, ip: str) -> None:
    _failures[_key(email, ip)].append(time.time())


def reset(email: str, ip: str) -> None:
    _failures.pop(_key(email, ip), None)


def reset_all(email: str) -> None:
    """Clear every bucket for an email (used after a password reset)."""
    prefix = f"{email.strip().lower()}|"
    for k in [k for k in _failures if k.startswith(prefix)]:
        _failures.pop(k, None)
