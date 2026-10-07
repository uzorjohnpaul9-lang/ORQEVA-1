"""Dedicated admin bot (TELEGRAM_BOT_TOKEN_ADMIN) preference + fallback."""


def test_admin_token_prefers_admin_env(monkeypatch):
    from payments.admin_bot import _admin_token

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_FREE", "free-token")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_ADMIN", "admin-token")
    assert _admin_token() == "admin-token"

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN_ADMIN")
    assert _admin_token() == "free-token"


def test_channel_notifier_admin_alert_uses_admin_token(monkeypatch):
    from notifications.channel_notifier import ChannelNotifier

    sent = []
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_FREE", "free-token")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_ADMIN", "admin-token")

    notifier = ChannelNotifier()
    monkeypatch.setattr(
        notifier, "_send_telegram", lambda token, chat, msg: sent.append((token, chat))
    )
    notifier.send_admin_alert("hello")
    assert sent == [("admin-token", "42")]


def test_channel_notifier_falls_back_to_tier_bot(monkeypatch):
    from notifications.channel_notifier import ChannelNotifier

    sent = []
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_FREE", "free-token")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN_ADMIN", raising=False)

    notifier = ChannelNotifier()
    monkeypatch.setattr(
        notifier, "_send_telegram", lambda token, chat, msg: sent.append((token, chat))
    )
    notifier.send_admin_alert("hello")
    assert sent == [("free-token", "42")]


def test_live_engine_exposes_admin_bot_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN_ADMIN", "admin-token")

    from live_engine import TelegramNotifier

    notifier = TelegramNotifier()
    assert notifier.bot_tokens["admin"] == "admin-token"
