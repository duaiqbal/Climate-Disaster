"""
backend/main.py
================
Disaster DSS — FastAPI application entry point.

All endpoints are optional online enhancements. The Flutter app works
fully offline without this server. The backend provides:

  /health              — liveness probe
  /alerts              — CRUD for official disaster alerts
  /auth/register       — user registration
  /auth/login          — authentication
  /knowledge/search    — semantic/keyword search (laptop SQLite)
  /knowledge/chunks    — paginated chunk browser
  /knowledge/meta      — offline package metadata
  /sync/status         — latest package version info
  /sync/updates        — version history
  /sync/publish        — publish new build (admin)

Start:
    cd backend
    python -m uvicorn main:app --reload --port 8000

Environment variables:
    DATABASE_URL       — SQLite (default) or postgres+asyncpg://...
    ADMIN_API_KEY      — key for write endpoints (default: dev key)
    SECRET_KEY         — token signing key
    SQL_ECHO           — set to "1" to log SQL queries
    CORS_ORIGINS       — comma-separated allowed origins (default: *)
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.database import init_db
from backend.models.db_models import HealthResponse
from backend.routers import alerts, auth, knowledge, sync, monitor

APP_VERSION = "1.0.0"


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup; nothing special on shutdown."""
    await init_db()
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Disaster DSS API",
    description=(
        "Optional online sync backend for the Disaster Decision-Support System "
        "for Chitral, KP. The mobile app is fully functional without this server."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# When CORS_ORIGINS env var is not set, allow common local development origins.
# allow_credentials=True cannot be used with wildcard "*" — browsers block it.
_raw_origins = os.getenv("CORS_ORIGINS", "")
if _raw_origins:
    origins = [o.strip() for o in _raw_origins.split(",")]
else:
    origins = [
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(alerts.router)
app.include_router(auth.router)
app.include_router(knowledge.router)
app.include_router(sync.router)
app.include_router(monitor.router)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        db="sqlite",
        timestamp=datetime.now(timezone.utc),
    )


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "service": "Disaster DSS API",
        "version": APP_VERSION,
        "docs": "/docs",
        "note": (
            "The mobile app works fully offline without this server. "
            "This API provides optional alert sync and package updates."
        ),
    })


# ── Global error handlers ─────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(500)
async def server_error(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs."},
    )
