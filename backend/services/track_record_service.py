"""Public, auditable track record for resolved signals.

The public ledger is intentionally narrow:

* only platform-wide signals (``user_id is null``), never a user's private row;
* only ``data_source == "live"`` rows count toward performance;
* simulated / unknown-provenance rows are reported as excluded, not blended in;
* no account identifiers, provider payloads or free-form metadata are exposed.

Resolution itself lives in :mod:`backend.services.outcome_service`; this module
only reads the immutable closed rows and shapes them for the public API.
"""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone

from backend.db.models import SIGNALS
from backend.db.supabase import SupabaseDB, now_iso, parse_dt
from backend.services.outcome_service import (
    DEFAULT_BAR_INTERVAL,
    DEFAULT_MAX_AGE_HOURS,
    FALLBACK_BAR_INTERVAL,
    RESOLUTION_VERSION,
    _f,
    cost_r,
)

PAGE_SIZE = 1000
MAX_ROWS = 50_000

PUBLIC_COLUMNS = (
    "id,symbol,market,direction,entry_price,stop_loss,take_profit,exit_price,"
    "outcome,status,created_at,resolved_at,r_multiple,data_source,strategy,"
    "resolution_basis,resolution_version"
)
# Older databases may not have the provenance columns yet. Read without them
# and flag those rows as "legacy" instead of failing the whole endpoint.
LEGACY_COLUMNS = (
    "id,symbol,market,direction,entry_price,stop_loss,take_profit,exit_price,"
    "outcome,status,created_at,resolved_at,r_multiple,data_source"
)

CSV_COLUMNS = [
    ("signal_id", "id"),
    ("opened_at", "created_at"),
    ("closed_at", "resolved_at"),
    ("symbol", "symbol"),
    ("market", "market"),
    ("direction", "direction"),
    ("entry", "entry_price"),
    ("stop", "stop_loss"),
    ("target", "take_profit"),
    ("exit", "exit_price"),
    ("outcome", "outcome"),
    ("r_multiple_gross", "r_multiple"),
    ("r_multiple_net", "r_multiple_net"),
    ("data_source", "data_source"),
    ("resolution_basis", "resolution_basis"),
]


def min_resolved() -> int:
    """Sample size required before a headline win rate is published."""
    try:
        return max(1, int(os.getenv("TRACK_RECORD_MIN_RESOLVED", "30")))
    except ValueError:
        return 30


def _num(value) -> float | None:
    return _f(value)


def _public_row(r: dict, cost: float) -> dict:
    rmul = _num(r.get("r_multiple"))
    net = round(rmul - cost, 4) if rmul is not None else None
    return {
        "signal_id": r.get("id"),
        "opened_at": r.get("created_at"),
        "closed_at": r.get("resolved_at"),
        "symbol": r.get("symbol"),
        "market": r.get("market"),
        "direction": r.get("direction"),
        "entry": _num(r.get("entry_price")),
        "stop": _num(r.get("stop_loss")),
        "target": _num(r.get("take_profit")),
        "exit": _num(r.get("exit_price")),
        "outcome": r.get("outcome"),
        "r_multiple": rmul,
        "r_multiple_net": net,
        "data_source": r.get("data_source"),
        "resolution_basis": r.get("resolution_basis") or "legacy",
        "resolution_version": r.get("resolution_version") or RESOLUTION_VERSION,
        "strategy": r.get("strategy"),
    }


def _dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return parse_dt(value)
    except (TypeError, ValueError):
        return None


def aggregate(rows: list[dict], *, cost: float | None = None,
              gate: int | None = None) -> dict:
    """Aggregate raw signal rows into the public performance summary."""
    cost = cost_r() if cost is None else cost
    gate = min_resolved() if gate is None else gate

    live_rows: list[dict] = []
    excluded = {"simulated": 0, "unknown": 0}
    for r in rows:
        src = r.get("data_source")
        if src != "live":
            excluded["simulated" if src == "simulated" else "unknown"] += 1
            continue
        if r.get("outcome"):
            live_rows.append(r)

    tp = sl = expired = breakeven = 0
    r_sum = r_net_sum = 0.0
    r_count = 0
    by_market: dict[str, dict] = {}
    by_strategy: dict[str, dict] = {}
    first_live: datetime | None = None
    last_resolved: datetime | None = None

    for r in live_rows:
        outcome = r.get("outcome")
        win = outcome == "tp"
        if outcome == "tp":
            tp += 1
        elif outcome == "sl":
            sl += 1
        elif outcome == "expired":
            expired += 1
        elif outcome == "breakeven":
            breakeven += 1

        rmul = _num(r.get("r_multiple"))
        if rmul is not None:
            r_sum += rmul
            r_net_sum += rmul - cost
            r_count += 1

        market = r.get("market") or "unknown"
        m = by_market.setdefault(market, {"resolved": 0, "wins": 0})
        m["resolved"] += 1
        m["wins"] += 1 if win else 0

        strategy = r.get("strategy")
        if strategy:
            s = by_strategy.setdefault(strategy, {"resolved": 0, "wins": 0, "markets": set()})
            s["resolved"] += 1
            s["wins"] += 1 if win else 0
            if r.get("market"):
                s["markets"].add(market)

        created = _dt(r.get("created_at"))
        if created and (first_live is None or created < first_live):
            first_live = created
        resolved = _dt(r.get("resolved_at"))
        if resolved and (last_resolved is None or resolved > last_resolved):
            last_resolved = resolved

    resolved_count = len(live_rows)
    markets = [
        {
            "market": name,
            "resolved": m["resolved"],
            "wins": m["wins"],
            "losses": m["resolved"] - m["wins"],
            "win_rate": round(m["wins"] / m["resolved"] * 100, 1) if m["resolved"] else 0.0,
        }
        for name, m in by_market.items()
    ]
    markets.sort(key=lambda x: x["resolved"], reverse=True)

    strategies = [
        {
            "strategy": name,
            "markets": sorted(s["markets"]),
            "resolved": s["resolved"],
            "wins": s["wins"],
            "losses": s["resolved"] - s["wins"],
            "win_rate": round(s["wins"] / s["resolved"] * 100, 1) if s["resolved"] else 0.0,
        }
        for name, s in by_strategy.items()
    ]
    strategies.sort(key=lambda x: x["resolved"], reverse=True)

    tp_sl = tp + sl
    return {
        "status": "live" if resolved_count >= gate else "collecting",
        "sample": {
            "resolved": resolved_count,
            "needed": gate,
            "remaining": max(0, gate - resolved_count),
            "progress_pct": round(min(100.0, resolved_count / gate * 100), 1) if gate else 100.0,
        },
        "resolved": resolved_count,
        "wins": tp,
        "losses": resolved_count - tp,
        "tp": tp,
        "sl": sl,
        "expired": expired,
        "breakeven": breakeven,
        "win_rate": round(tp / resolved_count * 100, 1) if resolved_count else 0.0,
        "win_rate_tp_sl": round(tp / tp_sl * 100, 1) if tp_sl else None,
        "avg_r_gross": round(r_sum / r_count, 3) if r_count else 0.0,
        "avg_r_net": round(r_net_sum / r_count, 3) if r_count else 0.0,
        "cost_r": cost,
        "by_market": markets,
        "by_strategy": strategies,
        "excluded": excluded,
        "first_live_at": first_live.isoformat() if first_live else None,
        "last_resolved_at": last_resolved.isoformat() if last_resolved else None,
        "live_only": True,
    }


async def _fetch_rows(db: SupabaseDB) -> tuple[list[dict], str]:
    """Closed/expired platform signals, newest schema first."""
    columns = PUBLIC_COLUMNS
    basis = "provenance"
    try:
        rows = await _page(db, columns)
        return rows, basis
    except Exception:
        # Pre-migration database: drop the new columns rather than 500 the API.
        rows = await _page(db, LEGACY_COLUMNS)
        return rows, "legacy"


async def _page(db: SupabaseDB, columns: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while offset < MAX_ROWS:
        page = await db.fetch_all(
            SIGNALS,
            where={
                "status": ["closed", "expired"],
                "user_id": {"op": "is", "value": "null"},
            },
            columns=columns,
            order="id.asc",
            limit=PAGE_SIZE,
            offset=offset,
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


async def snapshot(db: SupabaseDB, *, recent_limit: int = 50) -> dict:
    """Build the public ledger payload. Reads only closed rows."""
    rows, schema = await _fetch_rows(db)
    cost = cost_r()
    summary = aggregate(rows, cost=cost)
    summary["schema"] = schema
    summary["generated_at"] = now_iso()
    summary["resolution_version"] = RESOLUTION_VERSION
    summary["methodology"] = {
        "version": RESOLUTION_VERSION,
        "live_only": True,
        "sample_gate": min_resolved(),
        "cost_r": cost,
        "bar_interval": DEFAULT_BAR_INTERVAL,
        "fallback_interval": FALLBACK_BAR_INTERVAL,
        "same_bar_policy": "stop_first",
        "expiry_hours": DEFAULT_MAX_AGE_HOURS,
        "win_rate": "tp / (tp + sl)",
        "note": (
            "Only resolved signals generated from live market data are counted. "
            "Simulated and unknown-provenance rows are excluded. Signals are "
            "resolved on bars that open after publication, so the bar containing "
            "the signal's creation cannot leak pre-signal price action."
        ),
    }

    live = [r for r in rows if r.get("data_source") == "live" and r.get("outcome")]
    live.sort(key=lambda r: _dt(r.get("resolved_at")) or datetime.min.replace(tzinfo=timezone.utc),
              reverse=True)
    summary["recent"] = [_public_row(r, cost) for r in live[:recent_limit]]
    return summary


def _csv_cell(value) -> str:
    text = "" if value is None else str(value)
    # Spreadsheet formula injection guard.
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow([label for label, _ in CSV_COLUMNS])
    for row in rows:
        writer.writerow([_csv_cell(row.get(key)) for _, key in CSV_COLUMNS])
    return buf.getvalue()
