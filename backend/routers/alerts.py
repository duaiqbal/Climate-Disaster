"""
backend/routers/alerts.py
==========================
Disaster alert CRUD with full provenance (hard constraint 4),
alert lifecycle transitions, and audit history.

Every state change appends a row to AlertHistoryORM (append-only).
Alert creation persists source_id and ingestion_run_id FK links.
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

from core.config import settings
from database import get_db
from models.db_models import (
    AlertCreate,
    AlertDetailResponse,
    AlertHistoryORM,
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


def _append_history(
    db_session,
    alert: AlertORM,
    action: str,
    field_name: str,
    old_value: Optional[str],
    new_value: Optional[str],
    changed_by: str = "system",
) -> None:
    """Append an immutable history row — never update, never delete."""
    db_session.add(AlertHistoryORM(
        alert_db_id=alert.id,
        changed_at=datetime.now(timezone.utc),
        changed_by=changed_by,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        action=action,
    ))


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
@router.get("/{alert_id}", response_model=AlertDetailResponse)
async def get_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AlertORM).where(AlertORM.alert_id == alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")

    # Eagerly fetch history in the same session before closing
    hist_result = await db.execute(
        select(AlertHistoryORM)
        .where(AlertHistoryORM.alert_db_id == alert.id)
        .order_by(AlertHistoryORM.changed_at)
    )
    history_rows = hist_result.scalars().all()

    # Build response dict manually to avoid lazy-load outside session
    from models.db_models import AlertHistoryEntry
    alert_dict = {c.key: getattr(alert, c.key) for c in alert.__table__.columns}
    history_list = [
        AlertHistoryEntry.model_validate(
            {c.key: getattr(h, c.key) for c in h.__table__.columns}
        )
        for h in history_rows
    ]
    response = AlertDetailResponse(**alert_dict)
    response.history = history_list
    return response


# ── Create alert (admin) ──────────────────────────────────────────────────────
@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
async def create_alert(payload: AlertCreate, db: AsyncSession = Depends(get_db)):
    """Create alert — persists all provenance fields and opens audit trail."""
    body_hash = hashlib.sha256(payload.body.encode("utf-8")).hexdigest()

    alert = AlertORM(
        alert_id=str(uuid.uuid4())[:12],
        title=payload.title,
        body=payload.body,
        hazard_type=payload.hazard_type,
        severity=payload.severity,
        issued_at=payload.issued_at,
        published_at=payload.published_at,
        expires_at=payload.expires_at,
        source_org=payload.source_org,
        source_url=payload.source_url,
        source_id=payload.source_id,
        ingestion_run_id=payload.ingestion_run_id,
        fetch_timestamp=payload.fetch_timestamp or datetime.now(timezone.utc),
        content_hash=body_hash,
        verification_status=payload.verification_status,
        district=payload.district,
        province=payload.province,
        latitude=payload.latitude,
        longitude=payload.longitude,
        language=payload.language,
        is_active=True,
    )
    db.add(alert)
    await db.flush()  # get alert.id

    # Open audit trail with creation record
    _append_history(
        db, alert,
        action="created",
        field_name="verification_status",
        old_value=None,
        new_value=payload.verification_status,
    )
    await db.flush()
    await db.refresh(alert)

    # ── Broadcast new alert to all WebSocket clients instantly ────────────────
    try:
        from core.ws_manager import ws_manager
        if ws_manager.client_count > 0:
            alert_dict = AlertResponse.model_validate(alert).model_dump(mode="json")
            await ws_manager.broadcast_alert(alert_dict)
    except Exception:
        pass  # WS broadcast is best-effort — never fail the HTTP response
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

    old_status = alert.verification_status

    alert.title               = payload.title
    alert.body                = payload.body
    alert.hazard_type         = payload.hazard_type
    alert.severity            = payload.severity
    alert.issued_at           = payload.issued_at
    alert.source_org          = payload.source_org
    alert.source_url          = payload.source_url
    alert.source_id           = payload.source_id
    alert.ingestion_run_id    = payload.ingestion_run_id
    alert.content_hash        = hashlib.sha256(payload.body.encode()).hexdigest()
    alert.verification_status = payload.verification_status
    alert.district            = payload.district
    alert.province            = payload.province
    alert.latitude            = payload.latitude
    alert.longitude           = payload.longitude
    alert.language            = payload.language
    alert.updated_at          = datetime.now(timezone.utc)

    _append_history(
        db, alert,
        action="updated",
        field_name="verification_status",
        old_value=old_status,
        new_value=payload.verification_status,
    )

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

    old_state = alert.verification_status
    next_state = _TRANSITIONS.get(old_state)
    if not next_state:
        raise HTTPException(
            status_code=400,
            detail=f"Alert is already in terminal state '{old_state}'. No further transitions.",
        )

    alert.verification_status = next_state
    alert.updated_at          = datetime.now(timezone.utc)

    if next_state == "PUBLISHED":
        alert.published_at = datetime.now(timezone.utc)

    if next_state == "EXPIRED":
        alert.is_active = False

    # Append immutable history row
    _append_history(
        db, alert,
        action="transitioned",
        field_name="verification_status",
        old_value=old_state,
        new_value=next_state,
        changed_by=payload.note or "api",
    )

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
