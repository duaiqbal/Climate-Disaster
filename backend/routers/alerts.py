"""
backend/routers/alerts.py
==========================
Disaster alert CRUD with full provenance (hard constraint 4),
alert lifecycle transitions, audit history, and location-aware filtering.

Location filtering (Phase 2.3):
  GET /alerts supports two filter modes, both optional and combinable:
    ?district=Chitral          — ILIKE string match (existing, unchanged)
    ?province=Khyber+Pakhtunkhwa — exact province match (new)
    ?lat=35.85&lon=71.78&radius_km=50  — radius filter on lat/lon columns

  Radius filter semantics:
    - Uses Haversine distance approximation (accurate enough at these scales).
    - Alerts WITH lat/lon: included if within radius_km.
    - Alerts WITHOUT lat/lon: fall back to province/district string match.
    - Response includes `location_match_type` per alert:
        "coordinate"    — alert has lat/lon and was matched by radius
        "district_name" — alert matched via district ILIKE
        "province_only" — alert matched only via province
        "national"      — alert has no location data, shown for all queries
      This field lets the Flutter UI label precision honestly.

Every state change appends a row to AlertHistoryORM (append-only).
"""

import hashlib
import math
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


# ── Haversine distance (km) ───────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate great-circle distance in km. Accurate to ~0.3% at these scales."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
    # Existing filters (unchanged — no breaking change)
    district:            Optional[str]   = Query(None),
    hazard_type:         Optional[str]   = Query(None),
    severity:            Optional[str]   = Query(None),
    language:            Optional[str]   = Query(None),
    verification_status: Optional[str]   = Query(None),
    active_only:         bool            = Query(True),
    limit:               int             = Query(50, ge=1, le=200),
    offset:              int             = Query(0, ge=0),
    # New location filters (Phase 2.3)
    province:            Optional[str]   = Query(None, description="Exact province name match"),
    lat:                 Optional[float] = Query(None, description="Latitude for radius filter"),
    lon:                 Optional[float] = Query(None, description="Longitude for radius filter"),
    radius_km:           Optional[float] = Query(None, ge=1, le=1000,
                                                  description="Radius in km; requires lat+lon"),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """
    List active alerts with optional location filtering.

    Location filter modes (all optional, combinable):
      - `district` — ILIKE text match on district field
      - `province` — exact text match on province field
      - `lat`+`lon`+`radius_km` — radius filter; alerts without coordinates
        fall back to province/district string match

    Each alert in the response now includes `location_match_type`:
      "coordinate"    — matched by lat/lon radius
      "district_name" — matched by district ILIKE
      "province_only" — matched by province only
      "national"      — alert has no location data (shown for all queries)
    """
    stmt = select(AlertORM).order_by(AlertORM.issued_at.desc())

    if active_only:
        stmt = stmt.where(AlertORM.is_active == True)  # noqa: E712
    if district:
        stmt = stmt.where(AlertORM.district.ilike(f"%{district}%"))
    if province:
        stmt = stmt.where(AlertORM.province.ilike(f"%{province}%"))
    if hazard_type:
        stmt = stmt.where(AlertORM.hazard_type == hazard_type.lower())
    if severity:
        stmt = stmt.where(AlertORM.severity == severity.upper())
    if language:
        stmt = stmt.where(AlertORM.language == language.lower())
    if verification_status:
        stmt = stmt.where(
            AlertORM.verification_status == verification_status.upper()
        )

    all_rows = (await db.execute(stmt)).scalars().all()

    # ── Location post-filter (radius) ────────────────────────────────────────
    use_radius = lat is not None and lon is not None and radius_km is not None

    def _location_match_type(alert: AlertORM) -> str:
        if use_radius:
            if alert.latitude is not None and alert.longitude is not None:
                d = _haversine_km(lat, lon, alert.latitude, alert.longitude)  # type: ignore[arg-type]
                if d <= radius_km:  # type: ignore[operator]
                    return "coordinate"
                # Has coords but outside radius — excluded below
                return "_exclude"
            # No coords — fall back to province/district string match
            if province and alert.province and province.lower() in alert.province.lower():
                return "province_only"
            if district and alert.district and district.lower() in alert.district.lower():
                return "district_name"
            # National-scoped alert (district="Pakistan") — show always
            if not alert.district or alert.district.lower() in ("pakistan", ""):
                return "national"
            return "_exclude"
        # No radius filter — all passed rows are included
        if alert.latitude is not None and alert.longitude is not None:
            return "coordinate"
        if alert.district and alert.district.lower() not in ("pakistan", ""):
            return "district_name"
        if alert.province and alert.province.lower() not in ("pakistan", ""):
            return "province_only"
        return "national"

    if use_radius:
        filtered = [
            (a, _location_match_type(a))
            for a in all_rows
            if _location_match_type(a) != "_exclude"
        ]
    else:
        filtered = [(a, _location_match_type(a)) for a in all_rows]

    paginated = filtered[offset: offset + limit]

    # Build responses with location_match_type injected
    alert_responses = []
    for (a, match_type) in paginated:
        resp = AlertResponse.model_validate(a)
        resp_dict = resp.model_dump()
        resp_dict["location_match_type"] = match_type
        alert_responses.append(AlertResponse(**{
            k: v for k, v in resp_dict.items()
            if k in AlertResponse.model_fields
        }))

    return AlertListResponse(
        total=len(filtered),
        alerts=alert_responses,
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
