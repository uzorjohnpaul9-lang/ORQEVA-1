"""Signal holding-horizon (term) taxonomy.

Every signal is tagged with one of five terms. The term is a *target window*
derived from the data interval and the strategy's target distance - it is not a
promise that price reaches take-profit in that exact time.

This module is the single source of truth shared by the engines, the outcome
resolver, the API, Telegram, preferences and auto-trade. Keep the bands and
lifetimes here rather than scattering magic numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

TERM_ORDER: tuple[str, ...] = ("very_short", "short", "medium", "long", "very_long")
FAST_TERMS: tuple[str, ...] = ("very_short", "short")
DEFAULT_TERM = "very_long"


@dataclass(frozen=True)
class TermConfig:
    key: str
    label: str
    short_label: str
    target_min_minutes: int
    target_max_minutes: int
    data_interval: str
    resolver_interval: str
    max_age_hours: float
    decay_half_life_hours: float
    validity_floor: float
    grace_hours: float
    cooldown_minutes: int
    min_tier: str
    scan_interval_seconds: int
    paper_only: bool = False

    def horizon_label(self) -> str:
        if self.target_max_minutes <= 60:
            return f"{self.target_min_minutes}\u2013{self.target_max_minutes} min"
        if self.target_min_minutes < 60:
            return f"{self.target_min_minutes} min\u2013{self.target_max_minutes // 60}h"
        if self.target_max_minutes < 24 * 60:
            return f"{self.target_min_minutes // 60}\u2013{self.target_max_minutes // 60}h"
        return f"{self.target_min_minutes // (24 * 60)}\u2013{self.target_max_minutes // (24 * 60)} days"


_CONFIGS: dict[str, TermConfig] = {
    "very_short": TermConfig(
        key="very_short",
        label="Very short",
        short_label="5-15m",
        target_min_minutes=5,
        target_max_minutes=15,
        data_interval="1min",
        resolver_interval="1min",
        max_age_hours=20 / 60,
        decay_half_life_hours=10 / 60,
        validity_floor=0.20,
        grace_hours=2 / 60,
        cooldown_minutes=15,
        min_tier="vip",
        scan_interval_seconds=120,
        paper_only=True,
    ),
    "short": TermConfig(
        key="short",
        label="Short",
        short_label="15-60m",
        target_min_minutes=15,
        target_max_minutes=60,
        data_interval="5min",
        resolver_interval="1min",
        max_age_hours=2.0,
        decay_half_life_hours=40 / 60,
        validity_floor=0.30,
        grace_hours=5 / 60,
        cooldown_minutes=45,
        min_tier="vip",
        scan_interval_seconds=120,
        paper_only=True,
    ),
    "medium": TermConfig(
        key="medium",
        label="Medium",
        short_label="1-6h",
        target_min_minutes=60,
        target_max_minutes=6 * 60,
        data_interval="15min",
        resolver_interval="5min",
        max_age_hours=8.0,
        decay_half_life_hours=2.0,
        validity_floor=0.40,
        grace_hours=0.25,
        cooldown_minutes=120,
        min_tier="premium",
        scan_interval_seconds=900,
    ),
    "long": TermConfig(
        key="long",
        label="Long",
        short_label="6-24h",
        target_min_minutes=6 * 60,
        target_max_minutes=24 * 60,
        data_interval="1h",
        resolver_interval="1h",
        max_age_hours=24.0,
        decay_half_life_hours=12.0,
        validity_floor=0.50,
        grace_hours=0.5,
        cooldown_minutes=240,
        min_tier="premium",
        scan_interval_seconds=900,
    ),
    "very_long": TermConfig(
        key="very_long",
        label="Very long",
        short_label="1-5d",
        target_min_minutes=24 * 60,
        target_max_minutes=5 * 24 * 60,
        data_interval="1day",
        resolver_interval="1h",
        max_age_hours=72.0,
        decay_half_life_hours=12.0,
        validity_floor=0.50,
        grace_hours=1.0,
        cooldown_minutes=24 * 60,
        min_tier="free",
        scan_interval_seconds=900,
    ),
}

_ALIASES = {
    "very short": "very_short",
    "very-short": "very_short",
    "veryshort": "very_short",
    "scalp": "very_short",
    "quick": "very_short",
    "short": "short",
    "intraday": "short",
    "medium": "medium",
    "mid": "medium",
    "swing": "medium",
    "long": "long",
    "very long": "very_long",
    "very-long": "very_long",
    "verylong": "very_long",
    "position": "very_long",
    "daily": "very_long",
}


def normalize_term(value) -> str:
    """Return a valid term key; unknown/missing values fall back to very_long.

    The fallback preserves the behaviour of pre-migration swing signals.
    """
    if value is None:
        return DEFAULT_TERM
    key = str(value).strip().lower().replace(" ", "_")
    if key in _CONFIGS:
        return key
    return _ALIASES.get(str(value).strip().lower(), DEFAULT_TERM)


def get(term) -> TermConfig:
    return _CONFIGS[normalize_term(term)]


def is_valid_term(value) -> bool:
    if value is None:
        return False
    key = str(value).strip().lower().replace(" ", "_")
    return key in _CONFIGS or str(value).strip().lower() in _ALIASES


def all_terms() -> tuple[str, ...]:
    return TERM_ORDER


def label(term) -> str:
    return get(term).label


def short_label(term) -> str:
    return get(term).short_label


def horizon_label(term) -> str:
    return get(term).horizon_label()


def is_fast(term) -> bool:
    return normalize_term(term) in FAST_TERMS


def max_age_hours(term) -> float:
    return get(term).max_age_hours


def decay_half_life_hours(term) -> float:
    return get(term).decay_half_life_hours


def validity_floor(term) -> float:
    return get(term).validity_floor


def grace_hours(term) -> float:
    return get(term).grace_hours


def cooldown_minutes(term) -> int:
    return get(term).cooldown_minutes


def cooldown_hours(term) -> float:
    return cooldown_minutes(term) / 60.0


def min_tier(term) -> str:
    return get(term).min_tier


def paper_only(term) -> bool:
    return get(term).paper_only


def data_interval(term) -> str:
    return get(term).data_interval


def resolver_interval(term) -> str:
    return get(term).resolver_interval


def scan_interval_seconds(term) -> int:
    return get(term).scan_interval_seconds


def normalize_terms(values: Iterable | None) -> list[str]:
    """Normalise a user's term filter. Empty/invalid input means "no filter"."""
    if values is None:
        return []
    if isinstance(values, str):
        values = values.split(",")
    if not isinstance(values, (list, tuple, set)):
        return []
    out: list[str] = []
    for value in values:
        if not is_valid_term(value):
            continue
        term = normalize_term(value)
        if term not in out:
            out.append(term)
    return out
