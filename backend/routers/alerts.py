"""
backend/routers/alerts.py
==========================
Disaster alert CRUD with full provenance (hard constraint 4) and
alert lifecycle transitions.

Alert lifecycle:
  DISCOVERED → FETCHED → VALIDATED → OFFICIAL-VERIFIED → PUBLISHED → EXPIRED

GET  /alerts                       — list alerts (filterable)
GET  /alerts/{alert_id}            — single alert
POST /alerts                       — create alert (admin)
PUT  /alerts/{alert_id}            — update alert (admin)
DELETE /alerts/{alert_id}          — soft-delete (admin)
POST /alerts/{alert_id}/transition — advance lifecycle state (admin)
"""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.database import get_db
from backend.models.db_models import (
    AlertCreate,
    AlertListResponse,
    AlertORM,
    AlertResponse,
    VALID_ALERT_STATES,
)

router = APIRouter(prefix="/alerts", tags=["Alerts"])

_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def require_admin(key: Optional[str] = Security(_api_key_header)) -> None:
    if key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key.",
        )


# ── Lifecycle transition map ──────────────────────────────────────────────────
_TRANSITIONS: dict[str, str] = {
    "DISCOVERED":       "FETCHED",
    "FETCHED":          "VALIDATED",
    "VALIDATED":        "OFFICIAL-VERIFIED",
    "OFFICIAL-VERIFIED": "PUBLISHED",
    "PUBLISHED":        "EXPIRED",
}


# ── List alerts ───────────────────────────────────────────────────────────────
@router.get("", response_model=AlertListResponse)
async def list_alerts(
    district:     Optional[str] = Query(None),
    hazard_type:  Optional[str] = Query(None),
    severity:     Optional[str] = Query(None),
    language:     Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    active_only:  bool           = Query(True),
    limit:        int            = Query(50, ge=1, le=200),
    offset:       int            = Query(0, ge=0),
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
    if verification_status:
        stmt = stmt.where(AlertORM.verification_status == verification_status.upper())

    all_rows = (await db.execute(stmt)).scalars().all()
    paginated = all_rows[offset: offset + limit]
    return AlertListResponse(
        total=len(all_rows),
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
    """
    Create a new alert with full provenance (hard constraint 4).
    source_url, fetch_timestamp, content_hash, and verification_status
    are all persisted from the payload — never silently dropped.
    """
    # Compute content hash for deduplication / change detection
    body_hash = hashlib.sha256(payload.body.encode("utf-8")).hexdigest()

    alert = AlertORM(
        alert_id=str(uuid.uuid4())[:12],
        title=payload.title,
        body=payload.body,
        hazard_type=payload.hazard_type,
        severity=payload.severity,
        issued_at=payload.issued_at,
        # ── Provenance (hard constraint 4) ──────────────────────────────────
        source_org=payload.source_org,
        source_url=payload.source_url,                         # structured field
        fetch_timestamp=payload.fetch_timestamp or datetime.now(timezone.utc),
        content_hash=body_hash,                                # auto-computed
        verification_status=payload.verification_status,      # from payload
        # ── Geographic ──────────────────────────────────────────────────────
        district=payload.district,
        province=payload.province,
        # ── Content ─────────────────────────────────────────────────────────
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

    alert.title               = payload.title
    alert.body                = payload.body
    alert.hazard_type         = payload.hazard_type
    alert.severity            = payload.severity
    alert.issued_at           = payload.issued_at
    alert.source_org          = payload.source_org
    alert.source_url          = payload.source_url
    alert.content_hash        = hashlib.sha256(payload.body.encode()).hexdigest()
    alert.verification_status = payload.verification_status
    alert.district            = payload.district
    alert.province            = payload.province
    alert.language            = payload.language
    alert.updated_at          = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(alert)
    return AlertResponse.model_validate(alert)


# ── Lifecycle transition (admin) ──────────────────────────────────────────────
class TransitionRequest(BaseModel):
    note: Optional[str] = None  # optional human-readable reason


@router.post("/{alert_id}/transition", response_model=AlertResponse,
             dependencies=[Depends(require_admin)])
async def transition_alert(
    alert_id: str,
    payload: TransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Advance an alert to the next lifecycle state.

    State machine:
      DISCOVERED → FETCHED → VALIDATED → OFFICIAL-VERIFIED → PUBLISHED → EXPIRED

    EXPIRED alerts are automatically deactivated (is_active=False).
    """
    result = await db.execute(
        select(AlertORM).where(AlertORM.alert_id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

    current = alert.verification_status
    next_state = _TRANSITIONS.get(current)
    if not next_state:
        raise HTTPException(
            status_code=400,
            detail=f"Alert is already in terminal state '{current}'. No further transitions.",
        )

    alert.verification_status = next_state
    alert.updated_at          = datetime.now(timezone.utc)

    # EXPIRED alerts are automatically deactivated
    if next_state == "EXPIRED":
        alert.is_active = False

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
