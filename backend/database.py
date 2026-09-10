"""
backend/database.py
====================
SQLAlchemy async engine + session factory for the FastAPI backend.

Database: SQLite with aiosqlite (development / single-server deployment)
Upgrade path: swap DATABASE_URL to postgresql+asyncpg:// for production
with zero application-code changes.
"""

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# ── DB path ────────────────────────────────────────────────────────────────────
_DEFAULT_DB = str(Path(__file__).parent / "disaster_dss_backend.sqlite")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{_DEFAULT_DB}")

# ── Engine ─────────────────────────────────────────────────────────────────────
_connect_args = {}
if "sqlite" in DATABASE_URL:
    _connect_args["check_same_thread"] = False

engine = create_async_engine(
    DATABASE_URL,
    echo=bool(os.getenv("SQL_ECHO", "")),
    connect_args=_connect_args,
)

# ── Session factory ────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Base class for ORM models ──────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency — yields a DB session per request ──────────────────────────────
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Create all tables on startup ──────────────────────────────────────────────
async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
