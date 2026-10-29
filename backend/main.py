import sys
from pathlib import Path
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.db.database import init_db, readyz
from backend.api import auth, signals, portfolio, market, risk, dashboard, engine, trading, ai, exchanges, billing, billing_webhooks, preferences, notifications, admin, auto_trade, learn, calendar, telegram, support, affiliates, api_keys, metered, track_record
from backend.middleware.request_context import RequestContextMiddleware
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.middleware.sentinel import SentinelMiddleware
from backend.monitoring.metrics import MetricsMiddleware, render as render_metrics
from backend.services import scheduler

log = logging.getLogger("main")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

_STARTED_AT = time.time()

if settings.SECRET_KEY.startswith("dev-secret"):
    import warnings

    warnings.warn("SECRET_KEY is the development default - set a strong value before deploying")

if settings.sentry_active:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            release=settings.APP_VERSION,
            traces_sample_rate=0.0,
            send_default_pii=False,
        )
    except ImportError:
        import warnings

        warnings.warn("SENTRY_DSN is set but sentry-sdk is not installed - run pip install sentry-sdk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.start()
    yield
    await scheduler.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(MetricsMiddleware)
app.add_middleware(SentinelMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS
    or ["http://localhost:3000", "http://localhost:8000", "https://orqeva.pages.dev"],
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
# Outermost: every request (including sentinel 403s) gets a correlation id.
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log the stack trace and return a correlation id instead of a bare 500."""
    rid = getattr(request.state, "request_id", None) or "-"
    log.exception("unhandled error rid=%s path=%s", rid, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal", "request_id": rid},
        headers={"X-Request-ID": rid},
    )

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(signals.router)
app.include_router(portfolio.router)
app.include_router(market.router)
app.include_router(risk.router)
app.include_router(engine.router)
app.include_router(trading.router)
app.include_router(ai.router)
app.include_router(exchanges.router)
app.include_router(billing.router)
app.include_router(billing_webhooks.router)
app.include_router(admin.router)
app.include_router(preferences.router)
app.include_router(notifications.router)
app.include_router(auto_trade.router)
app.include_router(learn.router)
app.include_router(calendar.router)
app.include_router(telegram.router)
app.include_router(support.router)
app.include_router(affiliates.router)
app.include_router(affiliates.admin_router)
app.include_router(api_keys.router)
app.include_router(metered.router)
app.include_router(track_record.router)


@app.get("/api/health")
async def health():
    """Cheap liveness probe: no DB/VPN calls, safe for tight uptime monitors."""
    from backend.payments.registry import configured_gateways

    last = scheduler.get_last_scan()
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "uptime_s": int(time.time() - _STARTED_AT),
        "scanner": {
            "last_scan_at": (last or {}).get("at"),
            "last_scan_signals": (last or {}).get("signals_generated"),
        },
        "gateways": [g["provider"] for g in configured_gateways()],
    }


@app.get("/readyz")
async def ready():
    """Liveness + Supabase reachability for load balancers / uptime checks."""
    result = await readyz()
    if result.get("database") == "up":
        return {"status": "ready", "database": "up"}
    return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})


@app.get("/metrics")
async def metrics():
    body, ctype = render_metrics()
    return Response(content=body, media_type=ctype)