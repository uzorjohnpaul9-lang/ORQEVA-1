"""Economic calendar (scheduled market events) - keyless, free, fail-open.

Source: financecalendar.com JSON API. No API key; free for any use with
attribution (https://www.financecalendar.com). Responses are cached so repeated
dashboard/scheduler reads cost nothing and a source outage degrades to empty
results instead of errors.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from backend.middleware.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.financecalendar.com/wp-json/fc/v1"
CALENDAR_TTL = 3600  # seconds - the feed updates about hourly

ATTRIBUTION = {
    "source": "financecalendar.com",
    "url": "https://www.financecalendar.com",
}

# Event keyword -> markets it typically moves. Heuristic, presented as "may affect".
_ALL_MARKETS = ["commodity", "crypto", "forex", "stock"]
_US_MACRO = (
    "cpi", "ppi", "pce", "nfp", "nonfarm", "non-farm", "jobs", "jobless",
    "unemployment", "employment", "gdp", "inflation", "retail sales", "ism",
    "jolts", "interest rate", "fed", "fomc", "rate decision", "us ",
)
_CURRENCIES = {
    "eur": "forex", "gbp": "forex", "jpy": "forex", "chf": "forex",
    "cad": "forex", "aud": "forex", "nzd": "forex", "cny": "forex",
}


def _enabled() -> bool:
    return os.getenv("CALENDAR_ENABLED", "1").lower() not in ("0", "false", "no")


def _base_url() -> str:
    return (os.getenv("CALENDAR_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def alert_window_minutes() -> int:
    try:
        return max(1, int(os.getenv("EVENT_ALERT_WINDOW_MINUTES", "30")))
    except (TypeError, ValueError):
        return 30


def _clean(value: str | None) -> str:
    v = (value or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("\"", "'"):
        v = v[1:-1].strip()
    return v


def _markets_for(name: str, category: str = "") -> list[str]:
    """Best-effort list of markets an event may affect (sorted, deduped)."""
    text = f"{name} {category}".lower()
    if "central-bank" in text or "monetary-policy" in text or "fomc" in text:
        return list(_ALL_MARKETS)
    if any(k in text for k in _US_MACRO):
        return list(_ALL_MARKETS)
    markets: set[str] = set()
    if "gold" in text or "silver" in text:
        markets.add("commodity")
    if any(k in text for k in ("oil", "crude", "opec", "natural gas")):
        markets.update({"commodity", "stock"})
    if any(k in text for k in ("bitcoin", "crypto", "ethereum")):
        markets.add("crypto")
    for cur in _CURRENCIES:
        if cur in text:
            markets.add(_CURRENCIES[cur])
    if not markets:
        markets.update({"stock", "forex"})
    return sorted(markets)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize(event: dict[str, Any]) -> dict[str, Any]:
    name = event.get("name") or event.get("title") or "Event"
    category = event.get("category") or ""
    dt = _parse_time(event.get("time_utc"))
    return {
        "name": name,
        "title": event.get("title") or name,
        "impact": (event.get("impact") or "low").lower(),
        "category": category,
        "all_day": bool(event.get("all_day")),
        "date": event.get("date"),
        "time_utc": dt.isoformat() if dt else None,
        "time_et": event.get("time_et"),
        "consensus": event.get("consensus"),
        "prior": event.get("prior"),
        "actual": event.get("actual"),
        "url": event.get("url"),
        "affected_markets": _markets_for(name, category),
    }


# Sentinels so a failing source is cached briefly and stops costing latency.
_NEGATIVE = {"__calendar_none__": True}
NEGATIVE_TTL = 120  # seconds


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """One cached GET. Returns the JSON body, or None on any failure."""
    if not _enabled():
        return None
    key = f"cal:{path}:{params or {}}"
    cached = cache.get(key)
    if cached is not None:
        return None if isinstance(cached, dict) and cached.get("__calendar_none__") else cached
    try:
        r = requests.get(f"{_base_url()}/{path.lstrip('/')}", params=params or {}, timeout=15)
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            logger.warning("calendar error (%s): %s", path, str(data.get("error"))[:120])
            cache.set(key, _NEGATIVE, ttl=NEGATIVE_TTL)
            return None
        cache.set(key, data, ttl=CALENDAR_TTL)
        return data
    except Exception as e:  # outages must never break the app
        logger.warning("calendar fetch failed (%s): %s", path, str(e)[:120])
        cache.set(key, _NEGATIVE, ttl=NEGATIVE_TTL)
        return None


def upcoming(days: int = 7, impact: str | None = None) -> list[dict[str, Any]]:
    """Scheduled events from today through `days` ahead, soonest first."""
    days = max(1, min(int(days), 92))
    today = datetime.now(timezone.utc).date()
    params: dict[str, Any] = {
        "from": today.isoformat(),
        "to": (today + timedelta(days=days)).isoformat(),
        "limit": 500,
    }
    if impact:
        params["impact"] = impact
    data = _get("calendar", params)
    if not data:
        return []
    events = [_normalize(e) for e in data.get("events", []) if isinstance(e, dict)]
    events.sort(key=lambda e: e.get("time_utc") or "")
    return events


def today() -> list[dict[str, Any]]:
    """Today's scheduled events."""
    return upcoming(days=1)


def next_events(series: str | None = None) -> dict[str, Any]:
    """Next occurrence of a series (e.g. 'fomc', 'cpi') or the default feed."""
    params = {"series": series} if series else None
    data = _get("next", params)
    if not data:
        return {}
    ev = data.get("next")
    return _normalize(ev) if isinstance(ev, dict) else {}


def high_impact_soon(window_minutes: int = 30, now: datetime | None = None) -> list[dict[str, Any]]:
    """High-impact events landing inside the next `window_minutes`."""
    now = now or datetime.now(timezone.utc)
    horizon = now + timedelta(minutes=max(0, int(window_minutes)))
    soon: list[dict[str, Any]] = []
    for ev in upcoming(days=1, impact="high"):
        dt = _parse_time(ev.get("time_utc"))
        if dt and now <= dt <= horizon:
            ev = {**ev, "minutes_away": round((dt - now).total_seconds() / 60, 1)}
            soon.append(ev)
    return soon


def affected_markets(window_minutes: int = 30) -> set[str]:
    """Union of markets touched by any high-impact event inside the window."""
    markets: set[str] = set()
    for ev in high_impact_soon(window_minutes):
        markets.update(ev.get("affected_markets", []))
    return markets


def event_context(window_minutes: int | None = None) -> dict[str, Any] | None:
    """Compact summary of imminent high-impact events, for annotating signals.

    Returns None when nothing is imminent. Engines attach this to a signal's
    `indicators` so the UI can warn; no signal is suppressed.
    """
    window = window_minutes if window_minutes is not None else alert_window_minutes()
    active = high_impact_soon(window)
    if not active:
        return None
    return {
        "window_minutes": window,
        "events": [
            {
                "name": e.get("name"),
                "impact": e.get("impact"),
                "time_utc": e.get("time_utc"),
                "minutes_away": e.get("minutes_away"),
                "affected_markets": e.get("affected_markets", []),
            }
            for e in active
        ],
        "affected_markets": sorted({m for e in active for m in e.get("affected_markets", [])}),
        "attribution": ATTRIBUTION,
    }


def status() -> dict[str, Any]:
    return {
        "enabled": _enabled(),
        "base_url": _base_url(),
        "attribution": ATTRIBUTION,
    }
