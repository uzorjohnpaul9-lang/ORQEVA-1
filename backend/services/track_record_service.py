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
# Pre-fix rows were resolved against daily bars that included the signal's
# creation day (look-ahead). They are useful history but are not comparable to
# the corrected cohort, so the public headline starts at the integrity deploy.
DEFAULT_EPOCH = "2026-10-29T16:00:00Z"

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
    ("signal_id", "signal_id"),
    ("opened_at", "opened_at"),
    ("closed_at", "closed_at"),
    ("symbol", "symbol"),
    ("market", "market"),
    ("direction", "direction"),
    ("entry", "entry"),
    ("stop", "stop"),
    ("target", "target"),
    ("exit", "exit"),
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


def epoch() -> datetime | None:
    """Start of the comparable public cohort. Set TRACK_RECORD_EPOCH=off to disable."""
    raw = os.getenv("TRACK_RECORD_EPOCH", DEFAULT_EPOCH).strip()
    if raw.lower() in ("", "off", "none", "0"):
        return None
    try:
        value = parse_dt(raw)
    except (TypeError, ValueError):
        value = parse_dt(DEFAULT_EPOCH)
    if value is not None and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


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


def _tally(group: list[dict]) -> dict:
    stats = {
        "tp": 0, "sl": 0, "expired": 0, "breakeven": 0,
        "r_sum": 0.0, "r_count": 0,
        "by_market": {}, "by_strategy": {},
        "first_live": None, "last_resolved": None,
    }
    for r in group:
        outcome = r.get("outcome")
        if outcome in ("tp", "sl", "expired", "breakeven"):
            stats[outcome] += 1

        rmul = _num(r.get("r_multiple"))
        if rmul is not None:
            stats["r_sum"] += rmul
            stats["r_count"] += 1

        market = r.get("market") or "unknown"
        m = stats["by_market"].setdefault(market, {"resolved": 0, "wins": 0})
        m["resolved"] += 1
        m["wins"] += 1 if outcome == "tp" else 0

        strategy = r.get("strategy")
        if strategy:
            s = stats["by_strategy"].setdefault(
                strategy, {"resolved": 0, "wins": 0, "markets": set()}
            )
            s["resolved"] += 1
            s["wins"] += 1 if outcome == "tp" else 0
            if r.get("market"):
                s["markets"].add(market)

        created = _dt(r.get("created_at"))
        if created and (stats["first_live"] is None or created < stats["first_live"]):
            stats["first_live"] = created
        resolved = _dt(r.get("resolved_at"))
        if resolved and (stats["last_resolved"] is None or resolved > stats["last_resolved"]):
            stats["last_resolved"] = resolved
    return stats


def aggregate(rows: list[dict], *, cost: float | None = None,
              gate: int | None = None, since: datetime | None = None) -> dict:
    """Aggregate raw signal rows into the public performance summary.

    ``since`` is the start of the comparable cohort. Rows resolved before it are
    counted as ``legacy`` and reported separately, never in the headline.
    """
    cost = cost_r() if cost is None else cost
    gate = min_resolved() if gate is None else gate

    current: list[dict] = []
    legacy: list[dict] = []
    excluded = {"simulated": 0, "unknown": 0, "legacy": 0}
    for r in rows:
        src = r.get("data_source")
        if src != "live":
            excluded["simulated" if src == "simulated" else "unknown"] += 1
            continue
        if not r.get("outcome"):
            continue
        resolved_at = _dt(r.get("resolved_at"))
        if since is not None and (resolved_at is None or resolved_at < since):
            legacy.append(r)
            continue
        current.append(r)
    excluded["legacy"] = len(legacy)

    s = _tally(current)
    tp, sl = s["tp"], s["sl"]
    resolved_count = len(current)
    r_count = s["r_count"]
    r_net_sum = s["r_sum"] - cost * r_count
    tp_sl = tp + sl

    markets = [
        {
            "market": name,
            "resolved": m["resolved"],
            "wins": m["wins"],
            "losses": m["resolved"] - m["wins"],
            "win_rate": round(m["wins"] / m["resolved"] * 100, 1) if m["resolved"] else 0.0,
        }
        for name, m in s["by_market"].items()
    ]
    markets.sort(key=lambda x: x["resolved"], reverse=True)

    strategies = [
        {
            "strategy": name,
            "markets": sorted(v["markets"]),
            "resolved": v["resolved"],
            "wins": v["wins"],
            "losses": v["resolved"] - v["wins"],
            "win_rate": round(v["wins"] / v["resolved"] * 100, 1) if v["resolved"] else 0.0,
        }
        for name, v in s["by_strategy"].items()
    ]
    strategies.sort(key=lambda x: x["resolved"], reverse=True)

    legacy_cohort = None
    if legacy:
        ls = _tally(legacy)
        lt, ls_sl = ls["tp"], ls["sl"]
        legacy_cohort = {
            "resolved": len(legacy),
            "win_rate_tp_sl": round(lt / (lt + ls_sl) * 100, 1) if lt + ls_sl else None,
            "avg_r_gross": round(ls["r_sum"] / ls["r_count"], 3) if ls["r_count"] else 0.0,
            "note": "Resolved before the look-ahead fix; excluded from the public headline.",
        }

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
        "expired": s["expired"],
        "breakeven": s["breakeven"],
        "win_rate": round(tp / resolved_count * 100, 1) if resolved_count else 0.0,
        "win_rate_tp_sl": round(tp / tp_sl * 100, 1) if tp_sl else None,
        "avg_r_gross": round(s["r_sum"] / r_count, 3) if r_count else 0.0,
        "avg_r_net": round(r_net_sum / r_count, 3) if r_count else 0.0,
        "cost_r": cost,
        "by_market": markets,
        "by_strategy": strategies,
        "excluded": excluded,
        "legacy_cohort": legacy_cohort,
        "first_live_at": s["first_live"].isoformat() if s["first_live"] else None,
        "last_resolved_at": s["last_resolved"].isoformat() if s["last_resolved"] else None,
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
    start = epoch()
    summary = aggregate(rows, cost=cost, since=start)
    summary["schema"] = schema
    summary["cohort_started_at"] = start.isoformat() if start else None
    summary["generated_at"] = now_iso()
    summary["resolution_version"] = RESOLUTION_VERSION
    summary["methodology"] = {
        "version": RESOLUTION_VERSION,
        "live_only": True,
        "sample_gate": min_resolved(),
        "cost_r": cost,
        "cohort_started_at": start.isoformat() if start else None,
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

    live = [
        r for r in rows
        if r.get("data_source") == "live"
        and r.get("outcome")
        and (
            start is None
            or (
                (resolved := _dt(r.get("resolved_at"))) is not None
                and resolved >= start
            )
        )
    ]
    live.sort(key=lambda r: _dt(r.get("resolved_at")) or datetime.min.replace(tzinfo=timezone.utc),
              reverse=True)
    summary["recent"] = [_public_row(r, cost) for r in live[:recent_limit]]
    return summary


def _csv_cell(value) -> str:
    # Numbers stay numeric (negative R values must not look like formulas).
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value) if isinstance(value, float) else str(value)
    text = "" if value is None else str(value)
    # Spreadsheet formula injection guard for text cells only.
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
