"""Manually close a live broker-backed trade and record the actual fill.

Usage:
    python scripts/manual_close.py <trade_id> [--exit-price PRICE] [--dry-run]

The trade is closed at the broker first. Only when the broker confirms (or
reports that the position is already gone) is the local trade marked closed, so
a failed broker call can never paper-close a position that is still live.

Run it with the backend's production environment so the encrypted broker
credentials decrypt correctly, for example:

    railway run --service ORQEVA-1 -- python scripts/manual_close.py <trade_id>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.models import SIGNALS, TRADES, USERS  # noqa: E402
from backend.db.supabase import SupabaseDB, get_service_client  # noqa: E402
from backend.services import notification_service, order_executor, trade_service  # noqa: E402


def _live_conn(trade: dict) -> bool:
    return trade.get("exchange") not in (None, "", "paper")


async def _fallback_price(db: SupabaseDB, trade: dict) -> float | None:
    if trade.get("signal_id"):
        signal = await db.fetch_one(
            SIGNALS, {"id": trade["signal_id"]}, columns="exit_price,status,outcome"
        )
        if signal and signal.get("exit_price"):
            try:
                return float(signal["exit_price"])
            except (TypeError, ValueError):
                pass
    price = await order_executor.live_price(trade.get("market"), trade.get("symbol"))
    return float(price) if price else None


async def close_trade(trade_id: str, exit_price: float | None, dry_run: bool) -> dict:
    db = SupabaseDB(await get_service_client())
    trade = await db.fetch_one(TRADES, {"id": trade_id})
    if not trade:
        return {"ok": False, "detail": "trade not found"}
    if trade.get("status") != "open":
        return {"ok": False, "detail": f"trade is already {trade.get('status')}"}

    broker_result: dict | None = None
    already_closed = False
    conn = None
    if _live_conn(trade):
        conn = await order_executor.active_connection(db, trade["user_id"], trade.get("market"))
        if not conn:
            return {
                "ok": False,
                "detail": f"no active {trade.get('exchange')} connection for {trade.get('market')}",
            }
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "detail": "would close at broker",
                "trade": {k: trade.get(k) for k in ("id", "symbol", "side", "quantity")},
            }
        broker_result = await order_executor._broker_close(conn, trade)
        if not broker_result.get("ok"):
            detail = broker_result.get("detail")
            if not order_executor._already_closed(detail):
                return {"ok": False, "detail": f"broker rejected close: {detail}"}
            already_closed = True

    price = exit_price
    if price is None and broker_result:
        price = broker_result.get("close_price") or broker_result.get("filled_price")
    if price is None:
        price = await _fallback_price(db, trade)
    if not price or float(price) <= 0:
        return {"ok": False, "detail": "exit price unavailable - pass --exit-price"}

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would_record": {"trade_id": trade_id, "exit_price": float(price)},
            "broker": broker_result,
        }

    closed = await trade_service.close_trade(db, trade_id, float(price))
    if not closed:
        return {"ok": False, "detail": "could not update the trade record"}

    user = await db.fetch_one(USERS, {"id": trade["user_id"]}, columns="id,tier")
    if user:
        try:
            await notification_service.create(
                db, user["id"], "trade",
                f"Position closed: {closed.get('symbol')}",
                "P&L: "
                f"{'+' if float(closed.get('pnl') or 0) >= 0 else ''}"
                f"{float(closed.get('pnl') or 0):.2f} USD at {closed.get('exit_price')}",
            )
        except Exception:
            pass
        try:
            from backend.services import telegram_service

            await telegram_service.notify_user(
                db, user, "tp_sl", telegram_service.format_trade_closed(closed)
            )
        except Exception:
            pass

    return {
        "ok": True,
        "already_closed_at_broker": already_closed,
        "trade": {
            k: closed.get(k)
            for k in ("id", "symbol", "side", "quantity", "entry_price",
                      "exit_price", "pnl", "status", "closed_at")
        },
        "broker": broker_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trade_id")
    parser.add_argument("--exit-price", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(close_trade(args.trade_id, args.exit_price, args.dry_run))
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
