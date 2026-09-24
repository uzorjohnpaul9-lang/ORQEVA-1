from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

from backend.db.models import TRADES
from backend.db.supabase import SupabaseDB, parse_dt


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


async def get_closed_trades(db: SupabaseDB, user_id: str,
                            start: datetime | None = None,
                            end: datetime | None = None) -> list[dict]:
    where: dict = {"user_id": user_id, "status": "closed"}
    if start is not None:
        where["closed_at"] = {"op": "gte", "value": _iso(start)}
    if end is not None:
        where["closed_at"] = {"op": "lte", "value": _iso(end)}
    return await db.fetch_all(TRADES, where=where, order="closed_at.asc")


def _day_key(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d")


def pnl_series(trades: list[dict]) -> list[dict]:
    """Daily realized P&L + cumulative equity."""
    daily: dict[str, float] = defaultdict(float)
    for t in trades:
        daily[_day_key(parse_dt(t.get("closed_at")))] += float(t.get("pnl") or 0.0)

    out = []
    cum = 0.0
    for day in sorted(daily):
        cum += daily[day]
        out.append({"date": day, "pnl": round(daily[day], 2), "equity": round(cum, 2)})
    return out


def drawdown_series(trades: list[dict]) -> list[dict]:
    """Running drawdown from peak equity."""
    out = []
    cum = 0.0
    peak = 0.0
    for t in trades:
        cum += float(t.get("pnl") or 0.0)
        peak = max(peak, cum)
        dd = cum - peak
        out.append({
            "date": _day_key(parse_dt(t.get("closed_at"))),
            "drawdown": round(dd, 2),
            "drawdown_pct": round((dd / (100000.0 + peak) * 100), 3) if (100000.0 + peak) else 0.0,
        })
    return out


def win_loss_by_strategy(trades: list[dict]) -> list[dict]:
    agg: dict[str, dict] = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0})
    for t in trades:
        key = t.get("strategy") or "manual"
        pnl = float(t.get("pnl") or 0.0)
        agg[key]["wins" if pnl > 0 else "losses"] += 1
        agg[key]["pnl"] += pnl
    return [
        {
            "strategy": k,
            "wins": v["wins"],
            "losses": v["losses"],
            "win_rate": round(v["wins"] / max(v["wins"] + v["losses"], 1) * 100, 1),
            "total_pnl": round(v["pnl"], 2),
        }
        for k, v in sorted(agg.items(), key=lambda kv: -kv[1]["pnl"])
    ]


def correlation_matrix(trades: list[dict]) -> dict:
    """Correlation of daily P&L between markets (stock/forex/crypto/...)."""
    daily_by_market: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    all_days: set[str] = set()
    for t in trades:
        day = _day_key(parse_dt(t.get("closed_at")))
        mkt = t.get("market") or "other"
        daily_by_market[mkt][day] += float(t.get("pnl") or 0.0)
        all_days.add(day)

    markets = sorted(daily_by_market)
    if len(markets) < 2 or len(all_days) < 3:
        return {"markets": markets, "matrix": [[1.0] * len(markets) for _ in markets],
                "note": "not enough data for meaningful correlation"}

    days = sorted(all_days)
    data = np.array([
        [daily_by_market[m].get(d, 0.0) for d in days] for m in markets
    ])
    try:
        matrix = np.corrcoef(data).tolist()
    except Exception:
        matrix = [[1.0 if i == j else 0.0 for j in range(len(markets))] for i in range(len(markets))]
    matrix = [[round(float(v), 3) for v in row] for row in matrix]
    return {"markets": markets, "matrix": matrix}


def trades_to_csv(trades: list[dict]) -> str:
    """RFC 4180-ish CSV of closed trades."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "symbol", "market", "side", "quantity", "entry_price",
                "exit_price", "pnl", "strategy", "exchange", "opened_at", "closed_at"])
    for t in trades:
        w.writerow([
            t.get("id"), t.get("symbol"), t.get("market"), t.get("side"),
            t.get("quantity"), t.get("entry_price"),
            t.get("exit_price") if t.get("exit_price") is not None else "",
            t.get("pnl") if t.get("pnl") is not None else "",
            t.get("strategy") or "", t.get("exchange") or "",
            t.get("opened_at") or "",
            t.get("closed_at") or "",
        ])
    return buf.getvalue()


def parse_range(start_s: str | None, end_s: str | None, days: int | None) -> tuple[datetime | None, datetime | None]:
    """Parse ISO dates or fall back to trailing N days."""
    def _parse(s: str) -> datetime:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    end = _parse(end_s) if end_s else None
    if start_s:
        start = _parse(start_s)
    elif days:
        start = datetime.now(timezone.utc) - timedelta(days=days)
    else:
        start = None
    return start, end