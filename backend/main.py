"""
backend/main.py
================
Disaster DSS — FastAPI application entry point.

Run from project root:
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload

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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.core.config import settings
from backend.database import init_db
from backend.models.db_models import HealthResponse
from backend.routers import alerts, auth, knowledge, monitor, sync

APP_VERSION = "2.0.0"


# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Disaster DSS API",
    description=(
        "Offline-first Disaster Decision-Support System for Chitral, KP. "
        "The Flutter app works fully offline without this server. "
        "This API provides authentication, alerts, semantic search, and sync."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Rate limit error handler ───────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(alerts.router)
app.include_router(knowledge.router)
app.include_router(sync.router)
app.include_router(monitor.router)


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
