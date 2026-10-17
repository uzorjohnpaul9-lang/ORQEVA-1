"""Two-way Telegram bot webhook (Phase C).

Telegram posts chat updates here; we resolve the sender's linked account from
the chat id and reply with the requested command output.

This endpoint is intentionally public (Telegram is the caller), so authenticity
is enforced with Telegram's ``X-Telegram-Bot-Api-Secret-Token`` header compared
against ``TELEGRAM_WEBHOOK_SECRET``.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from backend.db.database import get_db
from backend.db.models import USERS
from backend.db.supabase import SupabaseDB
from backend.services import preferences_service as prefs_service
from backend.services import telegram_service as telegram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

HELP_TEXT = (
    "<b>TradeAI bot</b>\n"
    "Commands:\n"
    "/status - account + active filters\n"
    "/signals - latest signals for your tier\n"
    "/watch SYM,SYM - set watchlist (no args clears)\n"
    "/directions buy,sell - filter by side (no args clears)\n"
    "/minconf 0.6 - minimum confidence 0-1\n"
    "/digest on|off - weekly performance digest\n"
    "/mute, /unmute - pause/resume signal alerts\n"
    "/help - this message"
)

_TIER_SIGNAL_LIMIT = {"free": 3, "premium": 8, "vip": 20}


def parse_command(text: str | None) -> tuple[str | None, str]:
    """Split a raw message into (command, args).

    '/watch BTC,ETH' -> ('watch', 'BTC,ETH'); '/help@TradeAIbot' -> ('help', '').
    Non-command text yields (None, text).
    """
    if not text or not text.strip():
        return None, ""
    text = text.strip()
    if not text.startswith("/"):
        return None, text
    head, _, rest = text.partition(" ")
    command = head[1:]
    if "@" in command:
        command = command.split("@", 1)[0]
    return command.lower(), rest.strip()


def _secret_ok(header_value: str | None) -> bool:
    """Validate the webhook secret token when one is configured."""
    expected = (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    if not expected:
        logger.warning("TELEGRAM_WEBHOOK_SECRET not set - accepting unauthenticated updates")
        return True
    return header_value == expected


async def dispatch_command(
    db: SupabaseDB, user: dict | None, command: str | None, args: str, chat_id: str
) -> str:
    """Resolve a parsed command to a reply string. Pure-ish: only reads/writes
    preferences and signals via the supplied db facade."""
    if command in (None, "start", "help"):
        return HELP_TEXT

    if user is None:
        return (
            "This chat isn't linked to a TradeAI account yet.\n"
            "Open the web app \u2192 Settings \u2192 Telegram and paste this chat id: "
            f"<code>{chat_id}</code>"
        )

    if command == "status":
        prefs = await prefs_service.get_or_create(db, user["id"])
        watch = ", ".join(prefs.get("watchlist") or []) or "all symbols"
        dirs = ", ".join(prefs.get("directions") or []) or "both sides"
        return (
            f"<b>{user.get('username') or 'You'}</b> \u00b7 {user.get('tier', 'free')}\n"
            f"Signal alerts: {'on' if prefs.get('telegram_signals') else 'off'}\n"
            f"Watchlist: {watch}\n"
            f"Directions: {dirs}\n"
            f"Min confidence: {float(prefs.get('min_confidence') or 0):.2f}\n"
            f"Weekly digest: {'on' if prefs.get('telegram_weekly_digest') else 'off'}"
        )

    if command == "signals":
        from backend.services import signal_service

        tier = user.get("tier", "free")
        rows = await signal_service.list_signals(
            db, status="active", tier=tier, limit=_TIER_SIGNAL_LIMIT.get(tier, 3)
        )
        if not rows:
            return "No active signals right now."
        return "<b>Latest signals</b>\n" + "\n\n".join(
            telegram.format_signal_alert(s) for s in rows
        )

    if command == "watch":
        await prefs_service.update(db, user["id"], {"watchlist": [] if not args else args})
        prefs = await prefs_service.get_or_create(db, user["id"])
        watch = ", ".join(prefs.get("watchlist") or []) or "all symbols"
        return f"Watchlist set: {watch}"

    if command == "directions":
        await prefs_service.update(db, user["id"], {"directions": [] if not args else args})
        prefs = await prefs_service.get_or_create(db, user["id"])
        dirs = ", ".join(prefs.get("directions") or []) or "both sides"
        return f"Directions set: {dirs}"

    if command == "minconf":
        try:
            val = float(args)
        except (TypeError, ValueError):
            return "Usage: /minconf 0.6"
        await prefs_service.update(db, user["id"], {"min_confidence": val})
        return f"Minimum confidence set to {prefs_service._norm_min_confidence(val):.2f}"

    if command == "digest":
        on = args.lower() in ("on", "1", "yes", "true") if args else True
        await prefs_service.update(db, user["id"], {"telegram_weekly_digest": on})
        return f"Weekly digest {'enabled' if on else 'disabled'}."

    if command == "mute":
        await prefs_service.update(db, user["id"], {"telegram_signals": False})
        return "Signal alerts paused. Send /unmute to resume."

    if command == "unmute":
        await prefs_service.update(db, user["id"], {"telegram_signals": True})
        return "Signal alerts resumed."

    return "Unknown command. Send /help for the list."


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: SupabaseDB = Depends(get_db),
):
    if not _secret_ok(x_telegram_bot_api_secret_token):
        return JSONResponse(status_code=403, content={"ok": False, "detail": "forbidden"})

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}  # ack malformed payloads so Telegram stops retrying

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return {"ok": True}
    chat_id = str(chat_id)
    text = message.get("text")

    try:
        user = await db.fetch_one(USERS, {"telegram_chat_id": chat_id})
        command, args = parse_command(text)
        reply = await dispatch_command(db, user, command, args, chat_id)
        if reply:
            await telegram.send_message(chat_id, reply, (user or {}).get("tier", "free"))
    except Exception as e:
        logger.warning(f"telegram webhook error: {str(e)[:150]}")

    return {"ok": True}
