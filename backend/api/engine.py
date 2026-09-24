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
    engines = {}
    try:
        from engines.stock_engine import StockEngine
        e = StockEngine()
        engines["stock"] = {"active": e.is_market_hours(), "symbols": len(e.get_symbols())}
    except Exception as ex:
        engines["stock"] = {"active": False, "error": str(ex)}

    try:
        from engines.forex_engine import ForexEngine
        e = ForexEngine()
        engines["forex"] = {"active": e.is_market_hours(), "symbols": len(e.get_symbols())}
    except Exception as ex:
        engines["forex"] = {"active": False, "error": str(ex)}

    try:
        from engines.crypto_engine import CryptoEngine
        e = CryptoEngine()
        engines["crypto"] = {"active": e.is_market_hours(), "symbols": len(e.get_symbols())}
    except Exception as ex:
        engines["crypto"] = {"active": False, "error": str(ex)}

    return engines