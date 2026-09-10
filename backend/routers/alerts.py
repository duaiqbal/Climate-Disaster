"""
backend/routers/alerts.py
==========================
CRUD endpoints for disaster alerts.

GET  /alerts                   — list active alerts (filterable)
GET  /alerts/{alert_id}        — single alert by ID
POST /alerts                   — create alert (admin key required)
PUT  /alerts/{alert_id}        — update alert (admin key required)
DELETE /alerts/{alert_id}      — soft-delete alert (admin key required)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import (
    AlertCreate,
    AlertListResponse,
    AlertORM,
    AlertResponse,
)

router = APIRouter(prefix="/alerts", tags=["Alerts"])

# ── Admin key (set ADMIN_API_KEY env var in production) ───────────────────────
import os
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")
_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def require_admin(key: Optional[str] = Security(_api_key_header)) -> None:
    if key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key. Set X-Admin-Key header.",
        )


# ── List alerts ───────────────────────────────────────────────────────────────
@router.get("", response_model=AlertListResponse)
async def list_alerts(
    district: Optional[str] = Query(None, description="Filter by district"),
    hazard_type: Optional[str] = Query(None, description="flood|landslide|flash_flood"),
    severity: Optional[str] = Query(None, description="LOW|MEDIUM|HIGH|EXTREME"),
    language: Optional[str] = Query(None, description="en|ur|ru"),
    active_only: bool = Query(True, description="Return only active alerts"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AlertORM).order_by(AlertORM.issued_at.desc())

    if active_only:
        stmt = stmt.where(AlertORM.is_active == True)  # noqa: E712
    if district:
        stmt = stmt.where(AlertORM.district.ilike(f"%{district}%"))
    if hazard_type:
        stmt = stmt.where(AlertORM.hazard_type == hazard_type.lower())
    if severity:
        stmt = stmt.where(AlertORM.severity == severity.upper())
    if language:
        stmt = stmt.where(AlertORM.language == language.lower())

    total_result = await db.execute(stmt)
    all_rows = total_result.scalars().all()
    total = len(all_rows)

    paginated = all_rows[offset: offset + limit]
    return AlertListResponse(
        total=total,
        alerts=[AlertResponse.model_validate(a) for a in paginated],
    )


# ── Single alert ──────────────────────────────────────────────────────────────
@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AlertORM).where(AlertORM.alert_id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return AlertResponse.model_validate(alert)


# ── Create alert (admin) ──────────────────────────────────────────────────────
@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_alert(payload: AlertCreate, db: AsyncSession = Depends(get_db)):
    alert = AlertORM(
        alert_id=str(uuid.uuid4())[:8],
        title=payload.title,
        body=payload.body,
        hazard_type=payload.hazard_type,
        severity=payload.severity,
        issued_at=payload.issued_at,
        source_org=payload.source_org,
        district=payload.district,
        language=payload.language,
        is_active=True,
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return AlertResponse.model_validate(alert)


# ── Update alert (admin) ──────────────────────────────────────────────────────
@router.put("/{alert_id}", response_model=AlertResponse,
            dependencies=[Depends(require_admin)])
async def update_alert(
    alert_id: str,
    payload: AlertCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlertORM).where(AlertORM.alert_id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

    for field, value in payload.model_dump().items():
        setattr(alert, field, value)
    await db.flush()
    await db.refresh(alert)
    return AlertResponse.model_validate(alert)


# ── Soft delete (admin) ───────────────────────────────────────────────────────
@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AlertORM).where(AlertORM.alert_id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    alert.is_active = False
    await db.flush()
