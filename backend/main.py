"""
backend/main.py
================
Disaster DSS — FastAPI application entry point.

Run from project root:
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --reload

Environment variables (see backend/core/config.py):
    ENV              — development (default) | production
    SECRET_KEY       — JWT signing secret  [REQUIRED in production]
    ADMIN_API_KEY    — Admin endpoint key  [REQUIRED in production]
    DATABASE_URL     — SQLAlchemy DB URL   (default: SQLite)
    CORS_ORIGINS     — comma-separated allowed origins
    ACCESS_TOKEN_TTL — access token TTL in seconds  (default: 3600)
    REFRESH_TOKEN_TTL— refresh token TTL in seconds (default: 604800)
    RATE_LIMIT_LOGIN — rate limit for /auth/login    (default: 10/minute)
    SQL_ECHO         — set to "1" to log SQL
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.rate_limit import RateLimitMiddleware
from core.scheduler import start_scheduler, stop_scheduler
from database import init_db
from models.db_models import HealthResponse
from routers import alerts, auth, knowledge, monitor, sync
from routers import rag as rag_router
from routers import ws as ws_router

APP_VERSION = "2.0.0"
limiter = None  # Rate limiting handled at infrastructure level in production


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()   # starts alert monitor background job
    # Start WebSocket heartbeat ping every 30s
    import asyncio
    async def _ws_ping_loop():
        from core.ws_manager import ws_manager
        while True:
            await asyncio.sleep(30)
            try:
                await ws_manager.broadcast_ping()
            except Exception:
                pass
    asyncio.create_task(_ws_ping_loop())
    yield
    stop_scheduler()


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Disaster DSS API",
    description=(
        "Offline-first Disaster Decision-Support System for Chitral, KP. "
        "The Flutter app works fully offline without this server."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (disabled in ENV=test)
app.add_middleware(RateLimitMiddleware)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(alerts.router)
app.include_router(knowledge.router)
app.include_router(rag_router.router)
app.include_router(sync.router)
app.include_router(monitor.router)
app.include_router(ws_router.router)   # real-time WebSocket /ws/alerts


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        db="sqlite" if "sqlite" in settings.database_url else "postgres",
        env=settings.env,
        timestamp=datetime.now(timezone.utc),
    )


# ── Root ───────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "service": "Disaster DSS API",
        "version": APP_VERSION,
        "env": settings.env,
        "docs": "/docs",
    })


# ── Global error handlers ──────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(500)
async def server_error(request: Request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )
