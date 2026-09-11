"""
backend/tests/test_alerts.py
=============================
Tests for alert CRUD, provenance fields, and lifecycle transitions.
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient

ADMIN_KEY = "disaster-dss-dev-key-change-in-prod"

BASE_ALERT = {
    "title":       "Flood Warning Chitral River",
    "body":        "NDMA warns of rising Chitral River levels due to heavy monsoon rainfall.",
    "hazard_type": "flood",
    "severity":    "HIGH",
    "issued_at":   "2024-08-01T06:00:00",
    "source_org":  "NDMA",
    "source_url":  "https://ndma.gov.pk/advisories/test-advisory.pdf",
    "district":    "Chitral",
    "language":    "en",
    "verification_status": "OFFICIAL-VERIFIED",
}


# ── Create / Retrieve ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_alert_success(client: AsyncClient):
    resp = await client.post("/alerts", json=BASE_ALERT,
                              headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == BASE_ALERT["title"]
    assert data["source_url"] == BASE_ALERT["source_url"]        # provenance
    assert data["verification_status"] == "OFFICIAL-VERIFIED"    # persisted
    assert data["fetch_timestamp"] is not None                   # auto-set
    assert data["source_org"] == "NDMA"


@pytest.mark.asyncio
async def test_create_alert_without_admin_key(client: AsyncClient):
    resp = await client.post("/alerts", json=BASE_ALERT)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_alerts_empty(client: AsyncClient):
    resp = await client.get("/alerts")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["alerts"] == []


@pytest.mark.asyncio
async def test_list_alerts_after_create(client: AsyncClient):
    await client.post("/alerts", json=BASE_ALERT,
                       headers={"X-Admin-Key": ADMIN_KEY})
    resp = await client.get("/alerts")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    alert = resp.json()["alerts"][0]
    assert alert["source_url"] == BASE_ALERT["source_url"]
    assert alert["verification_status"] == "OFFICIAL-VERIFIED"


@pytest.mark.asyncio
async def test_get_alert_by_id(client: AsyncClient):
    create = await client.post("/alerts", json=BASE_ALERT,
                                headers={"X-Admin-Key": ADMIN_KEY})
    alert_id = create.json()["alert_id"]
    resp = await client.get(f"/alerts/{alert_id}")
    assert resp.status_code == 200
    assert resp.json()["alert_id"] == alert_id


@pytest.mark.asyncio
async def test_get_alert_not_found(client: AsyncClient):
    resp = await client.get("/alerts/nonexistent-id")
    assert resp.status_code == 404


# ── Provenance fields ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alert_has_full_provenance(client: AsyncClient):
    """Hard constraint 4: source_org, source_url, fetch_timestamp, verification_status."""
    resp = await client.post("/alerts", json=BASE_ALERT,
                              headers={"X-Admin-Key": ADMIN_KEY})
    data = resp.json()
    assert data["source_org"]          == "NDMA"
    assert data["source_url"]          == "https://ndma.gov.pk/advisories/test-advisory.pdf"
    assert data["fetch_timestamp"]     is not None
    assert data["verification_status"] == "OFFICIAL-VERIFIED"


@pytest.mark.asyncio
async def test_alert_without_source_url(client: AsyncClient):
    """source_url is optional but fetch_timestamp must still be set."""
    payload = {**BASE_ALERT}
    del payload["source_url"]
    resp = await client.post("/alerts", json=payload,
                              headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 201
    assert resp.json()["source_url"] is None
    assert resp.json()["fetch_timestamp"] is not None


# ── Lifecycle transitions ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lifecycle_transition_sequence(client: AsyncClient):
    """OFFICIAL-VERIFIED → PUBLISHED → EXPIRED."""
    create = await client.post("/alerts", json=BASE_ALERT,
                                headers={"X-Admin-Key": ADMIN_KEY})
    alert_id = create.json()["alert_id"]
    assert create.json()["verification_status"] == "OFFICIAL-VERIFIED"

    # OFFICIAL-VERIFIED → PUBLISHED
    resp = await client.post(f"/alerts/{alert_id}/transition",
                              json={}, headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 200
    assert resp.json()["verification_status"] == "PUBLISHED"
    assert resp.json()["is_active"] is True

    # PUBLISHED → EXPIRED (auto-deactivates)
    resp = await client.post(f"/alerts/{alert_id}/transition",
                              json={}, headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 200
    assert resp.json()["verification_status"] == "EXPIRED"
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_lifecycle_full_sequence_from_discovered(client: AsyncClient):
    """DISCOVERED → FETCHED → VALIDATED → OFFICIAL-VERIFIED → PUBLISHED → EXPIRED."""
    payload = {**BASE_ALERT, "verification_status": "DISCOVERED"}
    create = await client.post("/alerts", json=payload,
                                headers={"X-Admin-Key": ADMIN_KEY})
    alert_id = create.json()["alert_id"]

    expected_sequence = ["FETCHED", "VALIDATED", "OFFICIAL-VERIFIED", "PUBLISHED", "EXPIRED"]
    for expected_state in expected_sequence:
        resp = await client.post(f"/alerts/{alert_id}/transition",
                                  json={}, headers={"X-Admin-Key": ADMIN_KEY})
        assert resp.status_code == 200, f"Failed at transition to {expected_state}"
        assert resp.json()["verification_status"] == expected_state


@pytest.mark.asyncio
async def test_lifecycle_terminal_state_rejected(client: AsyncClient):
    """Cannot transition past EXPIRED."""
    payload = {**BASE_ALERT, "verification_status": "DISCOVERED"}
    create = await client.post("/alerts", json=payload,
                                headers={"X-Admin-Key": ADMIN_KEY})
    alert_id = create.json()["alert_id"]

    # Advance to EXPIRED
    for _ in range(5):
        await client.post(f"/alerts/{alert_id}/transition",
                           json={}, headers={"X-Admin-Key": ADMIN_KEY})

    # Try one more — should fail
    resp = await client.post(f"/alerts/{alert_id}/transition",
                              json={}, headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_transition_requires_admin(client: AsyncClient):
    create = await client.post("/alerts", json=BASE_ALERT,
                                headers={"X-Admin-Key": ADMIN_KEY})
    alert_id = create.json()["alert_id"]
    resp = await client.post(f"/alerts/{alert_id}/transition", json={})
    assert resp.status_code == 403


# ── Filters ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_by_district(client: AsyncClient):
    await client.post("/alerts", json=BASE_ALERT,
                       headers={"X-Admin-Key": ADMIN_KEY})
    resp = await client.get("/alerts?district=Chitral")
    assert resp.json()["total"] == 1
    resp2 = await client.get("/alerts?district=Peshawar")
    assert resp2.json()["total"] == 0


@pytest.mark.asyncio
async def test_filter_by_verification_status(client: AsyncClient):
    await client.post("/alerts", json=BASE_ALERT,
                       headers={"X-Admin-Key": ADMIN_KEY})
    resp = await client.get("/alerts?verification_status=OFFICIAL-VERIFIED")
    assert resp.json()["total"] == 1
    resp2 = await client.get("/alerts?verification_status=DISCOVERED")
    assert resp2.json()["total"] == 0


# ── Soft delete ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_soft_delete(client: AsyncClient):
    create = await client.post("/alerts", json=BASE_ALERT,
                                headers={"X-Admin-Key": ADMIN_KEY})
    alert_id = create.json()["alert_id"]
    del_resp = await client.delete(f"/alerts/{alert_id}",
                                    headers={"X-Admin-Key": ADMIN_KEY})
    assert del_resp.status_code == 204
    # Should not appear in active list
    resp = await client.get("/alerts?active_only=true")
    assert resp.json()["total"] == 0
