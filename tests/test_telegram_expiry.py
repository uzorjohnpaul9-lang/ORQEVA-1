"""Expiry DM fan-out: watchlist-scoped, opt-in, batched, and never raises."""
from backend.services import telegram_service


def _signal(symbol: str, market: str = "forex", direction: str = "buy",
            confidence: float = 0.60, **overrides) -> dict:
    row = {
        "symbol": symbol,
        "market": market,
        "direction": direction,
        "confidence": confidence,
        "created_at": "2026-01-01T00:00:00Z",
        "resolved_at": "2026-01-01T02:00:00Z",
        "exit_price": 1.1,
        "invalidation_reason": "confidence_decay",
    }
    row.update(overrides)
    return row


def _prefs(**overrides) -> dict:
    prefs = {
        "telegram_signals": True,
        "watchlist": ["XAU/USD"],
        "directions": [],
        "min_confidence": 0,
        "default_market": "all",
    }
    prefs.update(overrides)
    return prefs


class _UsersDB:
    def __init__(self, users):
        self.users = users

    async def fetch_all(self, *args, **kwargs):
        return self.users


def _user(uid: str = "u1", tier: str = "vip", chat: str | None = "123",
          email: str = "u1@example.com") -> dict:
    return {
        "id": uid,
        "tier": tier,
        "telegram_chat_id": chat,
        "is_active": True,
        "email": email,
    }


def _patch(monkeypatch, prefs, sent, token_tiers=None, detail="sent"):
    async def fake_prefs(db, uid):
        return prefs

    def fake_token(tier):
        if token_tiers is not None:
            token_tiers.append(tier)
        return "test-token"

    def fake_post(bot_token, chat_id, text):
        sent.append({"token": bot_token, "chat_id": chat_id, "text": text})
        return (detail == "sent"), detail

    monkeypatch.setattr(telegram_service.prefs_service, "get_or_create", fake_prefs)
    monkeypatch.setattr(telegram_service, "_bot_token", fake_token)
    monkeypatch.setattr(telegram_service, "_post_message", fake_post)


async def test_expiry_dm_only_covers_the_users_watchlist(monkeypatch):
    sent = []
    _patch(monkeypatch, _prefs(watchlist=["XAU/USD"]), sent)

    n = await telegram_service.broadcast_expired_signals(
        _UsersDB([_user()]),
        [_signal("XAU/USD", market="commodity"), _signal("EUR/USD"),
         _signal("BTC/USD", market="crypto")],
    )

    assert n == 1
    assert len(sent) == 1
    text = sent[0]["text"]
    assert "XAU/USD" in text
    assert "EUR/USD" not in text
    assert "BTC/USD" not in text


async def test_empty_watchlist_gets_no_expiry_dm(monkeypatch):
    sent = []
    _patch(monkeypatch, _prefs(watchlist=[]), sent)

    n = await telegram_service.broadcast_expired_signals(
        _UsersDB([_user()]), [_signal("XAU/USD", market="commodity")]
    )

    assert n == 0
    assert sent == []


async def test_opted_out_user_gets_no_expiry_dm(monkeypatch):
    sent = []
    _patch(monkeypatch, _prefs(telegram_signals=False), sent)

    n = await telegram_service.broadcast_expired_signals(
        _UsersDB([_user()]), [_signal("XAU/USD", market="commodity")]
    )

    assert n == 0
    assert sent == []


async def test_unlinked_user_gets_no_expiry_dm(monkeypatch):
    sent = []
    _patch(monkeypatch, _prefs(), sent)

    n = await telegram_service.broadcast_expired_signals(
        _UsersDB([_user(chat=None)]), [_signal("XAU/USD", market="commodity")]
    )

    assert n == 0
    assert sent == []


async def test_market_and_confidence_filters_are_honoured(monkeypatch):
    sent = []
    _patch(
        monkeypatch,
        _prefs(watchlist=["XAU/USD"], min_confidence=0.8),
        sent,
    )

    n = await telegram_service.broadcast_expired_signals(
        _UsersDB([_user()]),
        [_signal("XAU/USD", market="commodity", confidence=0.60)],
    )

    assert n == 0
    assert sent == []


async def test_tier_bot_token_is_used(monkeypatch):
    sent = []
    token_tiers = []
    _patch(monkeypatch, _prefs(watchlist=["BTC/USD"]), sent, token_tiers)

    n = await telegram_service.broadcast_expired_signals(
        _UsersDB([_user(tier="vip")]),
        [_signal("BTC/USD", market="crypto")],
    )

    assert n == 1
    assert token_tiers == ["vip"]
    assert sent[0]["token"] == "test-token"


async def test_expiry_message_is_capped(monkeypatch):
    monkeypatch.setenv("EXPIRY_ALERT_MAX_ITEMS", "1")
    sent = []
    _patch(monkeypatch, _prefs(watchlist=["XAU/USD", "BTC/USD"]), sent)

    n = await telegram_service.broadcast_expired_signals(
        _UsersDB([_user()]),
        [_signal("XAU/USD", market="commodity"), _signal("BTC/USD", market="crypto")],
    )

    assert n == 1
    text = sent[0]["text"]
    assert "and 1 more" in text
    assert text.count("Signal expired:") == 1


async def test_missing_bot_token_is_not_an_error(monkeypatch):
    sent = []
    _patch(monkeypatch, _prefs(), sent, detail="no_bot_token")

    n = await telegram_service.broadcast_expired_signals(
        _UsersDB([_user()]), [_signal("XAU/USD", market="commodity")]
    )

    assert n == 0
    assert len(sent) == 1
