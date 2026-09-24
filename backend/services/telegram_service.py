"""Telegram dispatch (Phase 13): per-user, preference-gated, never raises.

Bot tokens come from the trading system's tiered setup:
TELEGRAM_BOT_TOKEN / TELEGRAM_BOT_TOKEN_PREMIUM / TELEGRAM_BOT_TOKEN_VIP
"""
import asyncio
import logging
import os
from typing import Any

import requests

from backend.db.models import USERS
from backend.db.supabase import SupabaseDB
from backend.services import preferences_service as prefs_service

logger = logging.getLogger(__name__)

CATEGORIES = ("signals", "tp_sl", "market_analysis", "risk", "system")

_PREF_FIELD = {
    "signals": "telegram_signals",
    "tp_sl": "telegram_tp_sl",
    "market_analysis": "telegram_market_analysis",
    "risk": "telegram_risk_alerts",
    "system": "telegram_system_alerts",
}

# Tier gating: free tier does not receive trade-level alerts
_TIER_ALLOWED = {
    "free": {"signals", "system"},
    "premium": CATEGORIES,
    "vip": CATEGORIES,
}

_API_BASE = "https://api.telegram.org"


def _bot_token(tier: str) -> str:
    for name in (f"TELEGRAM_BOT_TOKEN_{tier.upper()}", "TELEGRAM_BOT_TOKEN"):
        tok = os.getenv(name, "")
        if tok:
            return tok
    return ""


def _post_message(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    if not bot_token:
        return False, "no_bot_token"
    try:
        r = requests.post(
            f"{_API_BASE}/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        data = r.json()
        if data.get("ok"):
            return True, "sent"
        return False, data.get("description", "telegram_error")[:120]
    except Exception as e:
        return False, str(e)[:120]


async def send_test(user: dict) -> dict:
    """Send a test message to the user's linked chat."""
    if not user.get("telegram_chat_id"):
        return {"ok": False, "detail": "not_linked"}
    ok, detail = await asyncio.to_thread(
        _post_message, _bot_token(user.get("tier", "free")), user.get("telegram_chat_id"),
        "<b>TradeAI</b>: test message - your Telegram alerts are working.",
    )
    return {"ok": ok, "detail": detail}


async def notify_user(db: SupabaseDB, user: dict, category: str, text: str) -> bool:
    """Send to one user if linked + opted in. Returns True when sent."""
    if category not in CATEGORIES or not user.get("telegram_chat_id"):
        return False
    prefs = await prefs_service.get_or_create(db, user["id"])
    if not prefs.get(_PREF_FIELD[category]):
        return False
    if category not in _TIER_ALLOWED.get(user.get("tier", "free"), {"signals", "system"}):
        return False
    ok, detail = await asyncio.to_thread(
        _post_message, _bot_token(user.get("tier", "free")), user.get("telegram_chat_id"), text
    )
    if not ok and detail != "no_bot_token":
        logger.warning(f"Telegram send to {user.get('email')} failed: {detail}")
    return ok


async def broadcast(db: SupabaseDB, category: str, texts_by_market: dict[str, str]) -> int:
    """Fan out to all opted-in users whose default_market matches.

    texts_by_market: {'all': txt, 'crypto': txt, ...} - a user gets the entry
    for their default_market, falling back to 'all'.
    """
    sent = 0
    users = await db.fetch_all(USERS, where={"is_active": True})
    for user in users:
        prefs = await prefs_service.get_or_create(db, user["id"])
        if not prefs.get(_PREF_FIELD[category]):
            continue
        market = prefs.get("default_market") if prefs.get("default_market") != "all" else "all"
        text = texts_by_market.get(market) or texts_by_market.get("all")
        if not text or not user.get("telegram_chat_id"):
            continue
        if category not in _TIER_ALLOWED.get(user.get("tier", "free"), {"signals", "system"}):
            continue
        ok, _ = await asyncio.to_thread(
            _post_message, _bot_token(user.get("tier", "free")), user.get("telegram_chat_id"), text
        )
        if ok:
            sent += 1
    return sent


def format_signal_alert(sig: dict) -> str:
    direction = (sig.get("direction") or "").upper()
    arrow = "\u2197" if direction == "BUY" else "\u2198"
    conf = float(sig.get("confidence", 0) or 0) * 100
    return (
        f"{arrow} <b>{sig.get('symbol', '?')}</b> ({sig.get('market', '?')})\n"
        f"Signal: <b>{direction or '?'}</b> @ {sig.get('price') or sig.get('entry_price', '?')}\n"
        f"Confidence: {conf:.0f}% | Strategy: {sig.get('strategy', 'ai')}"
    )


def format_trade_closed(trade: dict) -> str:
    pnl = float(trade.get("pnl") or 0)
    emoji = "\u2705" if pnl >= 0 else "\u274c"
    return (
        f"{emoji} <b>Position closed</b>\n"
        f"{trade.get('symbol', '?')} · P&L: <b>{'+' if pnl >= 0 else ''}{pnl:.2f}</b> USD"
    )


def _format_signal_alert_any(sig: Any) -> str:
    """Back-compat: accepts both dicts and attribute-style objects."""
    if isinstance(sig, dict):
        return format_signal_alert(sig)
    get = lambda name, default=None: getattr(sig, name, default)  # noqa: E731
    return format_signal_alert({
        "direction": get("direction", ""),
        "confidence": get("confidence", 0),
        "symbol": get("symbol", "?"),
        "market": get("market", "?"),
        "price": get("price", "?"),
        "entry_price": get("entry_price", None),
        "strategy": get("strategy", "ai"),
    })