import asyncio

from fastapi import APIRouter, Depends

from backend.db.database import get_db
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user, require_admin
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/engine", tags=["engine"])


@router.post("/scan")
async def run_engine_scan(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(require_admin),
):
    check_rate_limit(user["id"], user.get("tier", "free"))

    from backend.services import engine_service
    out = await engine_service.run_scan(db)
    return {
        "signals_generated": out["signals_generated"],
        "by_market": out["by_market"],
        "errors": out["errors"],
        "signals": [
            {
                "id": s.get("id"),
                "symbol": s.get("symbol"),
                "market": s.get("market"),
                "direction": s.get("direction"),
                "confidence": s.get("confidence"),
            }
            for s in out["saved"]
        ],
    }


@router.get("/status")
async def engine_status(user: dict = Depends(get_current_user)):
    # Engine constructors and market-calendar lookups touch provider SDKs
    # synchronously, so they run off the event loop.
    async def describe(module_path: str, cls_name: str) -> dict:
        def load():
            mod = __import__(module_path, fromlist=[cls_name])
            e = getattr(mod, cls_name)()
            return {"active": e.is_market_hours(), "symbols": len(e.get_symbols())}
        try:
            return await asyncio.to_thread(load)
        except Exception as ex:
            return {"active": False, "error": str(ex)}

    results = await asyncio.gather(
        describe("engines.stock_engine", "StockEngine"),
        describe("engines.forex_engine", "ForexEngine"),
        describe("engines.crypto_engine", "CryptoEngine"),
    )
    return dict(zip(("stock", "forex", "crypto"), results))