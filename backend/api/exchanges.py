import asyncio

from fastapi import APIRouter, Depends, HTTPException

from backend.db.database import get_db
from backend.db.models import EXCHANGE_CONNECTIONS, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso
from backend.auth import get_current_user
from backend.db.schemas import ExchangeConnect
from backend.exchanges import get_adapter, supported
from backend.middleware.rate_limiter import check_rate_limit
from security.security_manager import SecurityManager

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])

security = SecurityManager()


def _mask(secret: str, visible: int = 4) -> str:
    return f"...{secret[-visible:]}" if len(secret) > visible else "..."


def _view(conn: dict) -> dict:
    adapter = get_adapter(conn.get("exchange"))
    return {
        "id": conn.get("id"),
        "exchange": conn.get("exchange"),
        "display_name": adapter.display_name if adapter else (conn.get("exchange") or "").title(),
        "markets": adapter.markets if adapter else [],
        "is_paper": conn.get("is_paper"),
        "is_active": conn.get("is_active"),
        "key_masked": _mask(security.decrypt_data(conn["api_key_encrypted"])),
        "connected_at": conn.get("connected_at"),
        "last_checked": conn.get("last_checked"),
    }


async def _get_owned(db: SupabaseDB, conn_id: str, user_id: str) -> dict:
    conn = await db.fetch_one(EXCHANGE_CONNECTIONS, {"id": conn_id})
    if not conn or conn.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="connection not found")
    return conn


@router.get("/meta")
async def meta(user: dict = Depends(get_current_user)):
    """Adapters available for connection."""
    return [
        {
            "name": a.name,
            "display_name": a.display_name,
            "markets": a.markets,
            "needs_secret": a.needs_secret,
        }
        for a in supported()
    ]


@router.get("")
async def list_connections(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    conns = await db.fetch_all(
        EXCHANGE_CONNECTIONS,
        where={"user_id": user["id"]},
        order="connected_at.desc",
    )
    return [_view(c) for c in conns]


@router.post("/connect", status_code=201)
async def connect(
    body: ExchangeConnect,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    adapter = get_adapter(body.exchange)
    if not adapter:
        raise HTTPException(status_code=422, detail="unsupported exchange")
    # One connection per exchange per user
    existing = await db.fetch_one(
        EXCHANGE_CONNECTIONS,
        {"user_id": user["id"], "exchange": body.exchange},
        columns="id",
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"{body.exchange} already connected - disconnect first")

    # Validate credentials before persisting (network failures do not block saving)
    validation = await asyncio.to_thread(adapter.validate, body.api_key, body.api_secret or "", body.is_paper)

    conn = await db.insert(EXCHANGE_CONNECTIONS, {
        "id": gen_uuid(),
        "user_id": user["id"],
        "exchange": body.exchange,
        "api_key_encrypted": security.encrypt_data(body.api_key),
        "api_secret_encrypted": security.encrypt_data(body.api_secret or ""),
        "is_paper": body.is_paper,
        "is_active": bool(validation.get("ok")),
        "connected_at": now_iso(),
        "last_checked": now_iso(),
    })
    return {**_view(conn), "validation": validation}


@router.delete("/{conn_id}")
async def disconnect(
    conn_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    conn = await _get_owned(db, conn_id, user["id"])
    await db.delete(EXCHANGE_CONNECTIONS, {"id": conn["id"]})
    return {"status": "disconnected", "id": conn_id}


@router.post("/{conn_id}/test")
async def test_connection(
    conn_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Validate stored credentials against the live/paper endpoint."""
    check_rate_limit(user["id"], user.get("tier", "free"))
    conn = await _get_owned(db, conn_id, user["id"])
    adapter = get_adapter(conn.get("exchange"))
    if not adapter:
        raise HTTPException(status_code=500, detail=f"no adapter for '{conn.get('exchange')}'")

    api_key = security.decrypt_data(conn["api_key_encrypted"])
    api_secret = security.decrypt_data(conn["api_secret_encrypted"])

    result = await asyncio.to_thread(adapter.validate, api_key, api_secret, conn.get("is_paper"))

    await db.update(
        EXCHANGE_CONNECTIONS,
        {"is_active": bool(result.get("ok")), "last_checked": now_iso()},
        where={"id": conn["id"]},
    )
    conn["is_active"] = bool(result.get("ok"))
    conn["last_checked"] = now_iso()
    return {**result, **_view(conn)}


@router.get("/{conn_id}/account")
async def account_snapshot(
    conn_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Live account/balance snapshot through the adapter."""
    check_rate_limit(user["id"], user.get("tier", "free"))
    conn = await _get_owned(db, conn_id, user["id"])
    adapter = get_adapter(conn.get("exchange"))
    if not adapter:
        raise HTTPException(status_code=500, detail=f"no adapter for '{conn.get('exchange')}'")

    api_key = security.decrypt_data(conn["api_key_encrypted"])
    api_secret = security.decrypt_data(conn["api_secret_encrypted"])

    try:
        snapshot = await asyncio.to_thread(adapter.account, api_key, api_secret, conn.get("is_paper"))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:200])
    return {"exchange": conn.get("exchange"), "account": snapshot}