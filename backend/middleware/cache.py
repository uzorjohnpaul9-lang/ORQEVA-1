import time
from typing import Any
from collections import defaultdict


class TTLCache:
    """Simple in-memory TTL cache."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = 60

    def get(self, key: str) -> Any | None:
        if key in self._store:
            value, expires = self._store[key]
            if time.time() < expires:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int | None = None):
        self._store[key] = (value, time.time() + (ttl or self._default_ttl))

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()


cache = TTLCache()
