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


def _clean(value: str | None) -> str:
    """Trim whitespace and a single layer of wrapping quotes from an env value.

    Copy-pasted tokens/ids often carry a trailing newline or surrounding
    quotes; Telegram rejects those with 404 Not Found / chat not found.
    """
    v = (value or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("\"", "'"):
        v = v[1:-1].strip()
    return v


def _bot_token(tier: str) -> str:
    for name in (f"TELEGRAM_BOT_TOKEN_{tier.upper()}", "TELEGRAM_BOT_TOKEN"):
        tok = _clean(os.getenv(name))
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


# Channel fan-out: each signal is posted only to its own tier's channel.
_CHANNEL_CHAIN = {
    "free": ("free",),
    "premium": ("premium",),
    "vip": ("vip",),
}


def _channel_id(tier: str) -> str:
    return _clean(os.getenv(f"TELEGRAM_CHANNEL_{tier.upper()}"))


def channels_configured() -> bool:
    return any(_channel_id(t) for t in ("free", "premium", "vip"))


_LAST_CHANNEL_FANOUT: dict[str, Any] = {}


async def broadcast_channels(texts_by_tier: dict[str, str]) -> int:
    """Post each tier's message block to its own tier channel.

    texts_by_tier: {"free": txt, "premium": txt, "vip": txt}. Each entry is
    sent with that channel's own bot (the bot must be a channel admin).
    Returns the number of channel messages delivered. Never raises.
    """
    global _LAST_CHANNEL_FANOUT
    from datetime import datetime, timezone

    sent = 0
    results: dict[str, dict] = {}
    attempted = False
    for src_tier, text in texts_by_tier.items():
        if not text:
            continue
        for chan_tier in _CHANNEL_CHAIN.get(src_tier, (src_tier,)):
            channel_id = _channel_id(chan_tier)
            if not channel_id:
                results[chan_tier] = {"ok": False, "detail": "no_channel_id"}
                continue
            attempted = True
            ok, detail = await asyncio.to_thread(
                _post_message, _bot_token(chan_tier), channel_id, text
            )
            results[chan_tier] = {"ok": ok, "detail": detail}
            if ok:
                sent += 1
            elif detail != "no_bot_token":
                logger.warning(f"Telegram channel post failed ({chan_tier}): {detail}")
    if attempted:
        _LAST_CHANNEL_FANOUT = {
            "at": datetime.now(timezone.utc).isoformat(),
            "sent": sent,
            "results": results,
        }
    return sent


def last_channel_fanout() -> dict:
    return _LAST_CHANNEL_FANOUT


async def test_channel(tier: str) -> dict:
    """Post a test message to one tier's channel using the backend's config."""
    channel_id = _channel_id(tier)
    if not channel_id:
        return {"tier": tier, "ok": False, "detail": "no_channel_id"}
    ok, detail = await asyncio.to_thread(
        _post_message, _bot_token(tier), channel_id,
        f"<b>TradeAI</b>: channel test ({tier}) - posting works.",
    )
    return {"tier": tier, "ok": ok, "detail": detail}


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