"""
backend/routers/sync.py
========================
Package sync endpoint — tells the app if a newer offline package is available
and provides the latest package metadata for version comparison.

GET  /sync/status          — returns current package version + checksums
GET  /sync/updates         — list of all published package versions
POST /sync/publish         — publish a new package build (admin only)
"""

import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.database import get_db
from backend.models.db_models import PackageUpdateORM, PackageUpdateResponse

router = APIRouter(prefix="/sync", tags=["Sync"])

_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def require_admin(key=Security(_api_key_header)) -> None:
    if key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin key required.")


# ── Current package status ────────────────────────────────────────────────────
@router.get("/status", response_model=Optional[PackageUpdateResponse])
async def sync_status(db: AsyncSession = Depends(get_db)):
    """Returns the latest published package version, or null if none yet."""
    result = await db.execute(
        select(PackageUpdateORM).order_by(PackageUpdateORM.built_at.desc()).limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        return None
    return PackageUpdateResponse.model_validate(latest)


# ── List all versions ─────────────────────────────────────────────────────────
@router.get("/updates", response_model=list[PackageUpdateResponse])
async def list_updates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PackageUpdateORM).order_by(PackageUpdateORM.built_at.desc()).limit(20)
    )
    rows = result.scalars().all()
    return [PackageUpdateResponse.model_validate(r) for r in rows]


# ── Publish new package build (admin) ─────────────────────────────────────────

class PublishRequest(BaseModel):
    version: str
    built_at: datetime
    chunk_count: int
    knowledge_checksum: Optional[str] = None
    hazard_checksum: Optional[str] = None
    release_notes: Optional[str] = None


@router.post("/publish", response_model=PackageUpdateResponse,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def publish_package(payload: PublishRequest, db: AsyncSession = Depends(get_db)):
    update = PackageUpdateORM(
        version=payload.version,
        built_at=payload.built_at,
        chunk_count=payload.chunk_count,
        knowledge_checksum=payload.knowledge_checksum,
        hazard_checksum=payload.hazard_checksum,
        release_notes=payload.release_notes,
    )
    db.add(update)
    await db.flush()
    await db.refresh(update)
    return PackageUpdateResponse.model_validate(update)
