"""Notifications + preferences."""
import os

import httpx

from tests.conftest import register_and_login


async def test_telegram_webhook_secret_and_ack(client: httpx.AsyncClient):
    """Two-way bot webhook: secret-token auth + always-ack, never 500s."""
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = "test-secret"
    # blank the bot tokens so no real network call to api.telegram.org happens
    saved_tokens = {
        k: os.environ.pop(k) for k in list(os.environ) if k.startswith("TELEGRAM_BOT_TOKEN")
    }
    try:
        # missing secret -> rejected
        r = await client.post("/api/telegram/webhook",
                              json={"message": {"chat": {"id": 424242}, "text": "/help"}})
        assert r.status_code == 403

        # correct secret -> acknowledged even for an unknown chat
        headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}
        r = await client.post("/api/telegram/webhook", headers=headers,
                              json={"message": {"chat": {"id": 424242}, "text": "/help"}})
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # non-command text and update without a chat still ack
        r = await client.post("/api/telegram/webhook", headers=headers,
                              json={"message": {"chat": {"id": 424242}, "text": "hello"}})
        assert r.status_code == 200 and r.json()["ok"] is True
        r = await client.post("/api/telegram/webhook", headers=headers, json={"update_id": 1})
        assert r.status_code == 200 and r.json()["ok"] is True

        # malformed body is acked so Telegram stops retrying
        r = await client.post(
            "/api/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret",
                     "Content-Type": "application/json"},
            content=b"not-json")
        assert r.status_code == 200 and r.json()["ok"] is True
    finally:
        os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
        os.environ.update(saved_tokens)


async def test_notification_lifecycle(client: httpx.AsyncClient):
    # kill-switch activation (the triggering event) is admin-only by design
    H, _ = await register_and_login(client, admin=True)

    # trigger an event that creates a notification (kill switch)
    r = await client.post("/api/risk/kill-switch", headers=H,
                          json={"active": True, "reason": "notif test"})
    assert r.status_code == 200

    r = await client.get("/api/notifications", headers=H)
    body = r.json()
    assert any(n["type"] == "risk" for n in body["notifications"])
    unread_before = body["unread_count"]
    assert unread_before >= 1

    # read-all first (all notifications still unread here)
    r = await client.post("/api/notifications/read-all", headers=H)
    assert r.json()["marked"] >= 1
    assert (await client.get("/api/notifications/unread-count", headers=H)).json()["count"] == 0

    # marking an already-read one again is idempotent
    nid = body["notifications"][0]["id"]
    r = await client.post("/api/notifications/read", headers=H,
                          json={"notification_id": nid})
    assert r.status_code == 200


async def test_foreign_notification_hidden(client: httpx.AsyncClient):
    H1, _ = await register_and_login(client, admin=True)
    H2, _ = await register_and_login(client)

    await client.post("/api/risk/kill-switch", headers=H1,
                      json={"active": True, "reason": "iso"})
    listing = (await client.get("/api/notifications", headers=H1)).json()
    nid = listing["notifications"][0]["id"]

    r = await client.post("/api/notifications/read", headers=H2,
                          json={"notification_id": nid})
    assert r.status_code == 404

    # H2 sees nothing of H1's events
    other = (await client.get("/api/notifications", headers=H2)).json()
    assert all(n["id"] != nid for n in other["notifications"])


async def test_preferences_crud_and_validation(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)

    p = (await client.get("/api/preferences", headers=H)).json()
    assert p["telegram_signals"] is True and p["telegram_linked"] is False

    r = await client.put("/api/preferences", headers=H,
                         json={"default_market": "crypto", "risk_tolerance": "aggressive"})
    assert r.json()["default_market"] == "crypto"

    r = await client.put("/api/preferences", headers=H,
                         json={"risk_tolerance": "yolo"})
    assert r.status_code == 422


async def test_telegram_link_unlink(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)

    r = await client.post("/api/preferences/telegram/link", headers=H,
                          json={"chat_id": "123456789"})
    assert r.status_code == 200
    assert r.json()["telegram_chat_id"] == "123456789"

    r = await client.delete("/api/preferences/telegram/link", headers=H)
    assert r.json()["telegram_linked"] is False
