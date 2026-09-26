import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.db.database import init_db, readyz
from backend.api import auth, signals, portfolio, market, risk, dashboard, engine, trading, ai, exchanges, billing, preferences, notifications, admin, auto_trade
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.monitoring.metrics import MetricsMiddleware, render as render_metrics
from backend.services import scheduler

if settings.SECRET_KEY.startswith("dev-secret"):
    import warnings

    warnings.warn("SECRET_KEY is the development default - set a strong value before deploying")


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
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS
    or ["http://localhost:3000", "http://localhost:8000", "https://orqeva.pages.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(admin.router)
app.include_router(preferences.router)
app.include_router(notifications.router)
app.include_router(auto_trade.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


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