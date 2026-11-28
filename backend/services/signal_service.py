import math
import os
from datetime import datetime, timedelta, timezone

from backend.db.models import SIGNALS, TRADES, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso, parse_dt
from backend.services import signal_terms

# Delivery latency ladder (the "Signal latency" promise in the pricing matrix):
# a free user sees a signal five minutes after it is generated, premium after
# one minute, vip in real time.
RELEASE_DELAY_SECONDS = {"free": 300, "premium": 60, "vip": 0}

# Confidence split: a free-tier signal this strong is promoted to premium, so
# free users see the everyday subset while paying users see the best calls.
FREE_CONFIDENCE_CEILING = 0.75

_TIER_RANK = {"free": 0, "premium": 1, "vip": 2}
_SEE_TIERS = {
    "free": ["free"],
    "premium": ["free", "premium"],
    "vip": ["free", "premium", "vip"],
}


def release_delay(tier: str | None) -> int:
    """Seconds a tier waits before a freshly generated signal becomes visible."""
    return RELEASE_DELAY_SECONDS.get((tier or "free").lower(), RELEASE_DELAY_SECONDS["free"])


def released_at_iso(tier: str | None, now: datetime | None = None) -> str:
    """Newest ``created_at`` a signal may have and still be visible to this tier."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=release_delay(tier))
    return cutoff.isoformat().replace("+00:00", "Z")


def is_released(signal: dict, tier: str | None, now: datetime | None = None) -> bool:
    """True when the signal has aged past this tier's latency window."""
    created = parse_dt(signal.get("created_at"))
    if created is None:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - created).total_seconds() >= release_delay(tier)


def _signal_row(s: dict) -> dict:
    row = dict(s)
    row.setdefault("status", "active")
    row.setdefault("term", signal_terms.DEFAULT_TERM)
    row["direction"] = (row.get("direction") or "").lower()
    return row


def _expires_at_iso(term: str, start=None) -> str:
    """Absolute deadline for a term, stored on the row as expires_at."""
    start_dt = parse_dt(start) if start else datetime.now(timezone.utc)
    hours = signal_terms.max_age_hours(term)
    return (start_dt + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


async def _insert_signal(db: SupabaseDB, row: dict) -> dict:
    try:
        return await db.insert(SIGNALS, row)
    except Exception:
        legacy = _strip_term_columns([row])
        return (await db.insert_many(SIGNALS, legacy))[0]


async def _insert_signals(db: SupabaseDB, rows: list[dict]) -> list[dict]:
    try:
        return await db.insert_many(SIGNALS, rows)
    except Exception:
        return await db.insert_many(SIGNALS, _strip_term_columns(rows))


def _strip_term_columns(rows: list[dict]) -> list[dict]:
    """Fallback for a database that has not run the term migration yet."""
    return [
        {k: v for k, v in row.items()
         if k not in ("term", "timeframe", "resolution_interval")}
        for row in rows
    ]


async def save_signal(db: SupabaseDB, symbol: str, market: str, direction: str,
                      confidence: float, entry_price: float, stop_loss: float,
                      take_profit: float, strategy: str, tier: str = "free",
                      indicators: dict | None = None, data_source: str = "live",
                      term: str = signal_terms.DEFAULT_TERM,
                      timeframe: str | None = None) -> dict:
    term = signal_terms.normalize_term(term)
    created_at = now_iso()
    row = {
        "id": gen_uuid(),
        "user_id": None,
        "symbol": symbol,
        "market": market,
        "direction": direction.lower(),
        "confidence": confidence,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "strategy": strategy,
        "status": "active",
        "tier_required": tier,
        "indicators": indicators,
        "data_source": data_source,
        "term": term,
        "timeframe": timeframe or signal_terms.data_interval(term),
        "resolution_interval": signal_terms.resolver_interval(term),
        "created_at": created_at,
        "expires_at": _expires_at_iso(term, created_at),
    }
    return await _insert_signal(db, row)


async def save_signals_batch(db: SupabaseDB, signals: list[dict]) -> list[dict]:
    rows = []
    for s in signals:
        term = signal_terms.normalize_term(s.get("term"))
        created_at = now_iso()
        rows.append({
            "id": gen_uuid(),
            "user_id": None,
            "symbol": s["symbol"],
            "market": s["market"],
            "direction": s["direction"].lower(),
            "confidence": s["confidence"],
            "entry_price": s.get("entry_price"),
            "stop_loss": s.get("stop_loss"),
            "take_profit": s.get("take_profit"),
            "strategy": s.get("strategy"),
            "status": "active",
            "tier_required": s.get("tier", "free"),
            "indicators": s.get("indicators"),
            "data_source": s.get("data_source") or "live",
            "term": term,
            "timeframe": s.get("timeframe") or signal_terms.data_interval(term),
            "resolution_interval": s.get("resolution_interval") or signal_terms.resolver_interval(term),
            "created_at": created_at,
            "expires_at": _expires_at_iso(term, created_at),
        })
    return await _insert_signals(db, rows)


async def list_signals(db: SupabaseDB, market: str | None = None,
                       status: str | None = None, tier: str = "free",
                       limit: int = 50, released_only: bool = True,
                       term: str | None = None) -> list[dict]:
    # Default-deny: an unrecognised tier must not see anything, otherwise a
    # corrupt/typo'd tier value silently unlocks every gated signal.
    allowed = _SEE_TIERS.get((tier or "").lower())
    if allowed is None:
        return []

    where: dict = {"tier_required": allowed}
    if market:
        where["market"] = market
    if status:
        where["status"] = status
    if term:
        where["term"] = signal_terms.normalize_term(term)
    if released_only:
        # Latency ladder: a tier only sees signals older than its own delay.
        where["created_at"] = {"op": "lte", "value": released_at_iso(tier)}
    try:
        return await db.fetch_all(SIGNALS, where=where, order="created_at.desc", limit=limit)
    except Exception:
        if "term" not in where:
            raise
        # Pre-migration database: the term column does not exist yet.
        where.pop("term", None)
        return await db.fetch_all(SIGNALS, where=where, order="created_at.desc", limit=limit)


def _teaser(signal: dict) -> dict:
    """Strip a locked signal down to a conversion teaser.

    Levels and indicators are removed so the teaser cannot be traded; the
    symbol, market, direction and confidence remain as the upgrade hook.
    """
    row = dict(signal)
    row["entry_price"] = None
    row["stop_loss"] = None
    row["take_profit"] = None
    row["indicators"] = None
    row["locked"] = True
    return row


async def locked_teasers(db: SupabaseDB, market: str | None = None,
                         status: str | None = None, tier: str = "free",
                         limit: int = 3, term: str | None = None) -> list[dict]:
    """Higher-tier signals the user cannot open yet, shown as locked teasers.

    The user's own latency window still applies so upcoming paid calls are not
    leaked ahead of schedule. Admins are handled by the caller.
    """
    user_tier = (tier or "").lower()
    if user_tier not in _SEE_TIERS:
        return []
    hidden = [t for t in ("free", "premium", "vip") if _TIER_RANK[t] > _TIER_RANK[user_tier]]
    if not hidden:
        return []

    where: dict = {
        "tier_required": hidden,
        "created_at": {"op": "lte", "value": released_at_iso(tier)},
    }
    if market:
        where["market"] = market
    if status:
        where["status"] = status
    if term:
        normalized = signal_terms.normalize_term(term)
        if user_tier != "vip" and signal_terms.is_fast(normalized):
            return []
        where["term"] = normalized
    elif user_tier != "vip":
        # Fast terms are a VIP-only lane: do not leak even their metadata as a
        # locked teaser to free/premium users.
        where["term"] = [t for t in signal_terms.all_terms() if not signal_terms.is_fast(t)]
    try:
        rows = await db.fetch_all(SIGNALS, where=where, order="created_at.desc", limit=limit)
    except Exception:
        if "term" not in where:
            raise
        where.pop("term", None)
        rows = await db.fetch_all(SIGNALS, where=where, order="created_at.desc", limit=limit)
    if user_tier != "vip":
        rows = [r for r in rows if not signal_terms.is_fast(r.get("term"))]
    return [_teaser(r) for r in rows]


def split_free_signals(signals: list[dict],
                       ceiling: float = FREE_CONFIDENCE_CEILING) -> int:
    """Promote strong free-tier signals to premium, mutating them in place.

    Returns how many were promoted. Used by the engine scan so the free plan
    sees the everyday subset and the confident calls sit behind an upgrade.
    """
    promoted = 0
    for s in signals:
        if s.get("tier") == "free" and float(s.get("confidence") or 0) >= ceiling:
            s["tier"] = "premium"
            promoted += 1
    return promoted


async def expire_old_signals(db: SupabaseDB, max_age_hours: int = 24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    await db.update(
        SIGNALS,
        {"status": "expired"},
        where={"status": "active", "created_at": {"op": "lt", "value": cutoff.isoformat().replace("+00:00", "Z")}},
    )


async def get_signal_stats(db: SupabaseDB):
    total = await db.count(SIGNALS)
    active = await db.count(SIGNALS, where={"status": "active"})
    # Page through in chunks so the per-market breakdown is not silently
    # truncated by PostgREST's 1000-row fetch cap.
    by_market: dict[str, int] = {}
    page_size = 1000
    offset = 0
    while True:
        rows = await db.fetch_all(SIGNALS, columns="market", limit=page_size, offset=offset)
        for r in rows:
            market = r.get("market")
            if market:
                by_market[market] = by_market.get(market, 0) + 1
        if len(rows) < page_size:
            break
        offset += page_size
    return {
        "total_signals": total,
        "active_signals": active,
        "by_market": by_market,
    }


async def get_signal(db: SupabaseDB, signal_id: str) -> dict | None:
    return await db.fetch_one(SIGNALS, {"id": signal_id})


# Confidence decay defaults are retained for callers that inspect the legacy
# constants. Per-term behaviour comes from signal_terms.TermConfig.
DECAY_HALF_LIFE_HOURS = 12.0


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# A live signal stops being valid when its decayed confidence falls below this
# floor. The minimum validity window keeps a signal issued exactly at the floor
# from expiring on the first resolver tick.
VALIDITY_MIN_CONFIDENCE = _env_float("SIGNAL_VALIDITY_MIN_CONFIDENCE", 0.50)
VALIDITY_GRACE_HOURS = max(0.0, _env_float("SIGNAL_VALIDITY_GRACE_HOURS", 1.0))
MAX_SIGNAL_AGE_HOURS = max(1.0, _env_float("SIGNAL_MAX_AGE_HOURS", 72.0))


def apply_decay(confidence: float, created_at, term: str | None = None) -> tuple[float, float]:
    """Return (effective_confidence, age_hours) with term-aware time decay."""
    confidence = float(confidence or 0.0)
    if created_at is None:
        return confidence, 0.0
    cfg = signal_terms.get(term)
    created = parse_dt(created_at)
    age_hours = max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 3600)
    effective = confidence * (0.5 ** (age_hours / cfg.decay_half_life_hours))
    return round(effective, 4), round(age_hours, 2)


def valid_until(confidence: float, created_at, term: str | None = None) -> datetime | None:
    """When the signal stops being valid if price never resolves it first."""
    if created_at is None:
        return None
    cfg = signal_terms.get(term)
    confidence = float(confidence or 0.0)
    created = parse_dt(created_at)
    if confidence <= cfg.validity_floor:
        hours = cfg.grace_hours
    else:
        hours = cfg.decay_half_life_hours * math.log2(confidence / cfg.validity_floor)
        hours = max(hours, cfg.grace_hours)
    return created + timedelta(hours=min(hours, cfg.max_age_hours))


def is_signal_valid(confidence: float, created_at, term: str | None = None) -> bool:
    """True while the signal is still inside its term's decay window."""
    cfg = signal_terms.get(term)
    effective, age = apply_decay(confidence, created_at, term=term)
    if age <= cfg.grace_hours:
        return True
    return effective >= cfg.validity_floor


def signal_validity(confidence: float, created_at, status: str | None = None,
                    resolved_at=None, term: str | None = None) -> dict:
    """Validity view shared by the API and the outcome resolver."""
    cfg = signal_terms.get(term)
    effective, age = apply_decay(confidence, created_at, term=term)
    state = (status or "active").lower()
    deadline = valid_until(confidence, created_at, term=term)
    reason: str | None = None
    valid = True

    if state == "expired":
        valid = False
        if created_at and resolved_at:
            created = parse_dt(created_at)
            resolved = parse_dt(resolved_at)
            life_hours = max(0.0, (resolved - created).total_seconds() / 3600)
            reason = (
                "confidence_decay"
                if life_hours < cfg.max_age_hours - 0.05
                else "time_expiry"
            )
        else:
            reason = (
                "confidence_decay"
                if effective < cfg.validity_floor
                else "time_expiry"
            )
    elif state == "cancelled":
        valid = False
        reason = "cancelled"
    elif state != "active":
        valid = False
    elif not is_signal_valid(confidence, created_at, term=term):
        valid = False
        reason = "confidence_decay"

    return {
        "valid": valid,
        "effective_confidence": effective,
        "age_hours": age,
        "invalidation_reason": reason,
        "valid_until": (
            deadline.isoformat().replace("+00:00", "Z") if deadline else None
        ),
        "term": signal_terms.normalize_term(term),
    }


async def accuracy_stats(db: SupabaseDB) -> dict:
    """Historical signal accuracy, derived from closed trades.

    Returns per-strategy and per-market outcome breakdown plus platform-wide
    signal counts (from the SIGNALS table), so the dashboard can show real
    signal-outcome analytics rather than an empty personal-trade view.
    """
    rows = await db.fetch_all(
        TRADES,
        where={"status": "closed"},
        columns="strategy,market,pnl",
    )

    grouped: dict[str, dict] = {}
    by_market: dict[str, dict] = {}
    overall_total = 0
    overall_wins = 0
    overall_pnl = 0.0

    for r in rows:
        strategy = r.get("strategy")
        market = r.get("market")
        pnl = float(r.get("pnl") or 0)
        win = pnl > 0

        overall_total += 1
        overall_wins += 1 if win else 0
        overall_pnl += pnl

        if strategy:
            g = grouped.setdefault(strategy, {
                "strategy": strategy,
                "markets": set(),
                "total": 0,
                "wins": 0,
                "total_pnl": 0.0,
            })
            g["markets"].add(market)
            g["total"] += 1
            if win:
                g["wins"] += 1
            g["total_pnl"] += pnl

        if market:
            m = by_market.setdefault(market, {"total": 0, "wins": 0, "total_pnl": 0.0})
            m["total"] += 1
            if win:
                m["wins"] += 1
            m["total_pnl"] += pnl

    strategies = []
    for g in grouped.values():
        strategies.append({
            "strategy": g["strategy"],
            "markets": sorted(m for m in g["markets"] if m),
            "closed_trades": g["total"],
            "wins": g["wins"],
            "losses": g["total"] - g["wins"],
            "win_rate": round(g["wins"] / g["total"] * 100, 1) if g["total"] else 0.0,
            "total_pnl": round(g["total_pnl"], 2),
        })
    strategies.sort(key=lambda s: s["win_rate"], reverse=True)

    markets = []
    for name, m in by_market.items():
        markets.append({
            "market": name,
            "closed_trades": m["total"],
            "wins": m["wins"],
            "losses": m["total"] - m["wins"],
            "win_rate": round(m["wins"] / m["total"] * 100, 1) if m["total"] else 0.0,
            "total_pnl": round(m["total_pnl"], 2),
        })
    markets.sort(key=lambda s: s["closed_trades"], reverse=True)

    from backend.services import outcome_service

    return {
        "overall": {
            "closed_trades": overall_total,
            "win_rate": round(overall_wins / overall_total * 100, 1) if overall_total else 0.0,
            "total_pnl": round(overall_pnl, 2),
        },
        "signals": await get_signal_stats(db),
        "outcomes": await outcome_service.outcome_stats(db),
        "strategies": strategies,
        "markets": markets,
    }