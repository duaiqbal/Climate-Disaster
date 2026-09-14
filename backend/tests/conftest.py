"""
backend/tests/conftest.py
==========================
Provides a fresh in-memory SQLite DB per test function.

Key design decisions:
  - event_loop is function-scoped to prevent state bleeding across tests
  - app lifespan is skipped (raise_app_exceptions only, no lifespan triggers)
    so init_db() never touches the real file-based SQLite during tests
  - get_db dependency is overridden to use an isolated in-memory engine
  - All tables are created fresh and dropped after each test
  - Imports use the same module path as the app (no 'backend.' prefix)
    so that dependency_overrides patches the exact same object the routers use
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure backend/ is on sys.path so "from database import ..." resolves
# to the same module object that all routers import — critical for
# dependency_overrides to work correctly.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

os.environ["ENV"] = "test"   # disables rate limiting middleware

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import using the SAME path routers use — not 'backend.database'
from database import Base, get_db
from main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
def event_loop():
    """Function-scoped event loop — prevents any state from leaking between tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def client():
    """
    Fresh in-memory SQLite + isolated AsyncClient per test.
    The app lifespan is disabled (raise_app_exceptions=True skips lifespan)
    so init_db() never runs against the real DB file during tests.
    """
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # Create all tables in the fresh in-memory DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_db

    # raise_app_exceptions=True is default; we do NOT pass lifespan=
    # so FastAPI's test client skips the lifespan startup (no init_db call).
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Teardown — clean slate for next test
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
