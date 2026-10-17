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


async def broadcast_signals(db: SupabaseDB, signals: list[dict]) -> int:
    """Per-user, filter-aware signal fan-out.

    Unlike :func:`broadcast` (which blasts one market blob), each user only
    receives the fresh signals that pass their watchlist / direction /
    min-confidence filters and their default_market. Returns messages sent.
    """
    fresh = [s for s in signals if s]
    if not fresh:
        return 0
    sent = 0
    users = await db.fetch_all(USERS, where={"is_active": True})
    for user in users:
        if not user.get("telegram_chat_id"):
            continue
        prefs = await prefs_service.get_or_create(db, user["id"])
        if not prefs.get(_PREF_FIELD["signals"]):
            continue
        if "signals" not in _TIER_ALLOWED.get(user.get("tier", "free"), {"signals", "system"}):
            continue
        market = prefs.get("default_market", "all")
        matched = [
            s for s in fresh
            if (market == "all" or s.get("market") == market)
            and prefs_service.matches_filters(prefs, s)
        ]
        if not matched:
            continue
        text = "<b>Engine scan</b>\n" + "\n\n".join(format_signal_alert(s) for s in matched)
        ok, detail = await asyncio.to_thread(
            _post_message, _bot_token(user.get("tier", "free")), user["telegram_chat_id"], text
        )
        if ok:
            sent += 1
        elif detail != "no_bot_token":
            logger.warning(f"Telegram signals to {user.get('email')} failed: {detail}")
    return sent


def format_weekly_digest(stats: dict, *, period_days: int = 7) -> str:
    """Render the weekly performance digest. Pure; tolerant of partial stats."""
    overall = stats.get("overall") or {}
    resolved = int(overall.get("resolved") or 0)
    wins = int(overall.get("wins") or 0)
    losses = int(overall.get("losses") or 0)
    win_rate = overall.get("win_rate")
    avg_r = overall.get("avg_r")
    generated = int(stats.get("generated") or 0)

    lines = [f"\U0001f4c8 <b>Weekly digest</b> (last {period_days} days)"]
    lines.append(
        f"Signals: <b>{generated}</b> | Resolved: <b>{resolved}</b> "
        f"(W {wins} / L {losses})"
    )
    if win_rate is not None:
        lines.append(f"Win rate: <b>{float(win_rate) * 100:.1f}%</b>")
    if avg_r is not None:
        lines.append(f"Avg R: <b>{float(avg_r):+.2f}</b>")

    by_market = stats.get("by_market") or {}
    ranked = sorted(
        by_market.items(),
        key=lambda kv: kv[1].get("win_rate") if kv[1].get("win_rate") is not None else -1,
        reverse=True,
    )
    for market, m in ranked[:3]:
        if not m.get("resolved"):
            continue
        rate = m.get("win_rate")
        rate_txt = f"{float(rate) * 100:.0f}%" if rate is not None else "-"
        lines.append(f"  \u2022 {str(market).replace('_', ' ').title()}: {rate_txt} ({m.get('resolved')})")

    if resolved == 0:
        lines.append("No resolved signals yet - check back next week.")
    return "\n".join(lines)


async def send_message(chat_id: str, text: str, tier: str = "free") -> bool:
    """Reply to a single chat (used by the two-way webhook). Never raises."""
    if not chat_id:
        return False
    ok, _ = await asyncio.to_thread(_post_message, _bot_token(tier), str(chat_id), text)
    return ok


async def send_weekly_digests(db: SupabaseDB, stats: dict | None = None) -> int:
    """Deliver the weekly digest to every opted-in, linked user.

    ``stats`` may be supplied (tests); otherwise it is pulled from
    outcome_service. Users must have telegram_weekly_digest enabled and be
    linked to a chat. Tier gating: 'signals' permission required. Never raises.
    """
    if stats is None:
        try:
            from backend.services import outcome_service

            stats = await outcome_service.forward_test_stats(db)
        except Exception as e:
            logger.warning(f"weekly digest stats unavailable: {str(e)[:120]}")
            stats = {}
    text = format_weekly_digest(stats)
    sent = 0
    try:
        users = await db.fetch_all(USERS, where={"is_active": True})
    except Exception as e:
        logger.warning(f"weekly digest user fetch failed: {str(e)[:120]}")
        return 0
    for user in users:
        if not user.get("telegram_chat_id"):
            continue
        if "signals" not in _TIER_ALLOWED.get(user.get("tier", "free"), {"signals", "system"}):
            continue
        prefs = await prefs_service.get_or_create(db, user["id"])
        if not prefs.get("telegram_weekly_digest"):
            continue
        ok, detail = await asyncio.to_thread(
            _post_message, _bot_token(user.get("tier", "free")), user["telegram_chat_id"], text
        )
        if ok:
            sent += 1
        elif detail != "no_bot_token":
            logger.warning(f"weekly digest to {user.get('email')} failed: {detail}")
    return sent


# Channel fan-out: a signal is posted to its own tier's channel and every
# higher tier's channel (cumulative), so VIP carries the most.
_CHANNEL_CHAIN = {
    "free": ("free", "premium", "vip"),
    "premium": ("premium", "vip"),
    "vip": ("vip",),
}


def _channel_id(tier: str) -> str:
    return _clean(os.getenv(f"TELEGRAM_CHANNEL_{tier.upper()}"))


def channels_configured() -> bool:
    return any(_channel_id(t) for t in ("free", "premium", "vip"))


_LAST_CHANNEL_FANOUT: dict[str, Any] = {}


async def broadcast_channels(texts_by_tier: dict[str, str]) -> int:
    """Post each tier's message block to its channel and every higher tier's.

    texts_by_tier: {"free": txt, "premium": txt, "vip": txt}. Each entry is
    sent with the target channel's own bot (each bot must be a channel admin).
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
    entry = sig.get("price") or sig.get("entry_price")
    sl = sig.get("stop_loss")
    tp = sig.get("take_profit")
    lines = [
        f"{arrow} <b>{sig.get('symbol', '?')}</b> ({sig.get('market', '?')})",
        f"Signal: <b>{direction or '?'}</b> @ {entry if entry is not None else '?'}",
    ]
    levels = []
    if sl is not None:
        levels.append(f"Stop: {sl}")
    if tp is not None:
        levels.append(f"Target: {tp}")
    if levels:
        lines.append(" | ".join(levels))
    lines.append(f"Confidence: {conf:.0f}% | Strategy: {sig.get('strategy', 'ai')}")
    return "\n".join(lines)


def format_trade_closed(trade: dict) -> str:
    pnl = float(trade.get("pnl") or 0)
    emoji = "\u2705" if pnl >= 0 else "\u274c"
    return (
        f"{emoji} <b>Position closed</b>\n"
        f"{trade.get('symbol', '?')} · P&L: <b>{'+' if pnl >= 0 else ''}{pnl:.2f}</b> USD"
    )


def format_event_alert(event: dict) -> str:
    """Event-ahead warning (routed under the 'risk' category)."""
    name = event.get("name") or "Economic event"
    mins = event.get("minutes_away")
    when = f"in {round(float(mins))} min" if isinstance(mins, (int, float)) else "soon"
    markets = ", ".join(event.get("affected_markets") or [])
    lines = [
        f"\u26a0 <b>High-impact event {when}</b>",
        name,
    ]
    if markets:
        lines.append(f"May affect: {markets}")
    lines.append("Consider tighter risk around the release.")
    return "\n".join(lines)


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
        "stop_loss": get("stop_loss", None),
        "take_profit": get("take_profit", None),
        "strategy": get("strategy", "ai"),
    })