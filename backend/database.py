"""
backend/database.py
====================
SQLAlchemy async engine + session factory.
Configuration comes from backend/core/config.py (never hardcoded here).
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

# ── Engine ─────────────────────────────────────────────────────────────────────
_connect_args = {}
if "sqlite" in settings.database_url:
    _connect_args["check_same_thread"] = False

engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
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


# ── Base class ─────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Request-scoped session dependency ─────────────────────────────────────────
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
