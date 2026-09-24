from datetime import datetime, timedelta, timezone

from backend.db.models import SIGNALS, TRADES, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso, parse_dt


def _signal_row(s: dict) -> dict:
    row = dict(s)
    row.setdefault("status", "active")
    row["direction"] = (row.get("direction") or "").lower()
    return row


async def save_signal(db: SupabaseDB, symbol: str, market: str, direction: str,
                      confidence: float, entry_price: float, stop_loss: float,
                      take_profit: float, strategy: str, tier: str = "free",
                      indicators: dict | None = None) -> dict:
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
        "created_at": now_iso(),
    }
    return await db.insert(SIGNALS, row)


async def save_signals_batch(db: SupabaseDB, signals: list[dict]) -> list[dict]:
    rows = []
    for s in signals:
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
            "created_at": now_iso(),
        })
    return await db.insert_many(SIGNALS, rows)


async def list_signals(db: SupabaseDB, market: str | None = None,
                       status: str | None = None, tier: str = "free",
                       limit: int = 50) -> list[dict]:
    where: dict = {}
    if tier == "free":
        where["tier_required"] = "free"
    elif tier == "premium":
        where["tier_required"] = ["free", "premium"]
    if market:
        where["market"] = market
    if status:
        where["status"] = status
    return await db.fetch_all(SIGNALS, where=where, order="created_at.desc", limit=limit)


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
    rows = await db.fetch_all(SIGNALS, columns="market")
    by_market: dict[str, int] = {}
    for r in rows:
        by_market[r["market"]] = by_market.get(r["market"], 0) + 1
    return {
        "total_signals": total,
        "active_signals": active,
        "by_market": by_market,
    }


async def get_signal(db: SupabaseDB, signal_id: str) -> dict | None:
    return await db.fetch_one(SIGNALS, {"id": signal_id})


# Confidence decay: exponential half-life of 12 hours.
# A signal generated 12h ago is worth half its original confidence.
DECAY_HALF_LIFE_HOURS = 12.0


def apply_decay(confidence: float, created_at) -> tuple[float, float]:
    """Return (effective_confidence, age_hours) with exponential time decay."""
    if created_at is None:
        return confidence, 0.0
    created = parse_dt(created_at)
    age_hours = max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 3600)
    effective = confidence * (0.5 ** (age_hours / DECAY_HALF_LIFE_HOURS))
    return round(effective, 4), round(age_hours, 2)


async def accuracy_stats(db: SupabaseDB) -> dict:
    """Historical signal accuracy per strategy, derived from closed trades."""
    rows = await db.fetch_all(
        TRADES,
        where={"status": "closed", "strategy": {"op": "neq", "value": None}},
        columns="strategy,market,pnl",
    )

    grouped: dict[str, dict] = {}
    for r in rows:
        strategy = r.get("strategy")
        if not strategy:
            continue
        g = grouped.setdefault(strategy, {
            "strategy": strategy,
            "markets": set(),
            "total": 0,
            "wins": 0,
            "total_pnl": 0.0,
        })
        g["markets"].add(r.get("market"))
        g["total"] += 1
        if (r.get("pnl") or 0) > 0:
            g["wins"] += 1
        g["total_pnl"] += float(r.get("pnl") or 0)

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
    overall_total = sum(s["closed_trades"] for s in strategies)
    overall_wins = sum(s["wins"] for s in strategies)
    return {
        "overall": {
            "closed_trades": overall_total,
            "win_rate": round(overall_wins / overall_total * 100, 1) if overall_total else 0.0,
        },
        "strategies": strategies,
    }