"""
backend/tests/test_phase2_alerts.py
=====================================
Regression tests for Phase 2:
  2.1  Multi-source monitor architecture
  2.2  Per-source health in /monitor/status
  2.3  Radius-based location filter on GET /alerts
"""

import importlib.util
import math
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[2]


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_module(rel: str, name: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # type: ignore[union-attr]
    return mod


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2.1 — Multi-source architecture
# ══════════════════════════════════════════════════════════════════════════════

class TestMultiSourceArchitecture:
    """official_alert_monitor.py must have 6 sources; each independent."""

    def _load_monitor(self):
        return _load_module("fetchers/official_alert_monitor.py", "monitor")

    def test_six_sources_configured(self):
        mon = self._load_monitor()
        assert len(mon.MONITOR_SOURCES) >= 6, (
            f"Expected >=6 sources, got {len(mon.MONITOR_SOURCES)}"
        )

    def test_all_sources_have_required_fields(self):
        mon = self._load_monitor()
        required = {"source_id", "source_org", "province", "district",
                    "page_url", "link_pattern", "hazard_type"}
        for src in mon.MONITOR_SOURCES:
            missing = required - src.keys()
            assert not missing, f"Source {src.get('source_id')} missing fields: {missing}"

    def test_province_field_populated_on_all_sources(self):
        mon = self._load_monitor()
        for src in mon.MONITOR_SOURCES:
            assert src.get("province"), (
                f"Source {src['source_id']} has empty province field"
            )

    def test_ndma_and_pdma_kp_present(self):
        mon = self._load_monitor()
        orgs = {s["source_org"] for s in mon.MONITOR_SOURCES}
        assert "NDMA" in orgs, "NDMA missing from sources"
        assert "PDMA KP" in orgs, "PDMA KP missing from sources"

    def test_pmd_present(self):
        mon = self._load_monitor()
        orgs = {s["source_org"] for s in mon.MONITOR_SOURCES}
        assert "PMD" in orgs, "PMD Flood Forecasting Division missing from sources"

    def test_pdma_punjab_present(self):
        mon = self._load_monitor()
        ids = {s["source_id"] for s in mon.MONITOR_SOURCES}
        assert "pdma_punjab" in ids, "PDMA Punjab not in sources"

    def test_alert_payload_has_province_field(self):
        """_process_source must build alerts with province as top-level field."""
        mon  = self._load_monitor()
        src  = mon.MONITOR_SOURCES[0]

        # Mock network + PDF extraction — test payload construction only
        fake_text  = (
            "NDMA Flood Advisory for Chitral district. Heavy rainfall warning "
            "issued. Flash flood alert. Emergency preparedness required."
        )
        fake_links = [{
            "url":        "https://ndma.gov.pk/test.pdf",
            "title":      "Test Advisory",
            "source_org": src["source_org"],
            "hazard_type": src["hazard_type"],
            "district":   src["district"],
            "province":   src["province"],
        }]

        captured: list[dict] = []
        state: dict = {"seen_urls": [], "last_run": None, "source_health": {}}
        seen: set   = set()

        with (
            patch.object(mon, "_fetch_page_links", return_value=fake_links),
            patch.object(mon, "_download_pdf"),
            patch.object(mon, "_extract_text_from_pdf", return_value=fake_text),
            patch.object(mon, "_post_alert", side_effect=lambda a: captured.append(a) or "test_id"),
        ):
            mon._process_source(src, seen, state, dry_run=False, run_ts="2026-09-14T00:00:00Z")

        assert len(captured) == 1, "Expected exactly 1 alert to be posted"
        alert = captured[0]
        assert "province" in alert, "province missing from alert payload"
        assert alert["province"] == src["province"], (
            f"province mismatch: {alert['province']!r} vs {src['province']!r}"
        )
        assert "source_url" in alert, "source_url missing from payload"
        assert "verification_status" in alert, "verification_status missing"
        assert alert["verification_status"] == "DISCOVERED"

    def test_one_source_failure_does_not_abort_others(self):
        """If one source's page fetch fails, others must still be processed."""
        mon   = self._load_monitor()
        state = {"seen_urls": [], "last_run": None, "source_health": {}}
        seen  = set()

        call_count = [0]

        def fake_fetch(source, seen_urls):
            call_count[0] += 1
            if source["source_id"] == "ndma_advisories":
                raise RuntimeError("simulated timeout")
            return []  # other sources return no new links — that's fine

        with patch.object(mon, "_fetch_page_links", side_effect=fake_fetch):
            results = []
            for src in mon.MONITOR_SOURCES:
                results.append(mon._process_source(
                    src, seen, state, dry_run=True, run_ts="2026-09-14T00:00:00Z"
                ))

        # All sources attempted
        assert call_count[0] == len(mon.MONITOR_SOURCES), (
            "Not all sources were attempted after one failure"
        )
        # Failed source has ok=False; others ok=True
        failed  = [r for r in results if not r["ok"]]
        success = [r for r in results if r["ok"]]
        assert len(failed) == 1, f"Expected 1 failed source, got {len(failed)}"
        assert len(success) >= 1, "At least one source should have succeeded"

    def test_deduplication_across_sources(self):
        """Same URL seen twice (from two sources) must not be processed twice."""
        mon   = self._load_monitor()
        state = {"seen_urls": [], "last_run": None, "source_health": {}}
        seen  = {"https://ndma.gov.pk/duplicate.pdf"}  # already seen

        fake_links = [{
            "url": "https://ndma.gov.pk/duplicate.pdf",  # in seen_urls
            "title": "Duplicate",
            "source_org": "NDMA",
            "hazard_type": "flood",
            "district": "Pakistan",
            "province": "Pakistan",
        }]

        posted: list = []
        with (
            patch.object(mon, "_fetch_page_links", return_value=fake_links),
            patch.object(mon, "_post_alert", side_effect=posted.append),
        ):
            result = mon._process_source(
                mon.MONITOR_SOURCES[0], seen, state, dry_run=False,
                run_ts="2026-09-14T00:00:00Z"
            )

        assert result["posted"] == 0, "Duplicate URL should not be re-posted"
        assert len(posted) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2.2 — Per-source health in /monitor/status
# ══════════════════════════════════════════════════════════════════════════════

class TestMonitorStatusPerSource:
    """GET /monitor/status must include per-source health breakdown."""

    def test_monitor_py_has_source_health_response(self):
        """MonitorStatusResponse schema must include sources list."""
        mon_mod = _load_module("backend/routers/monitor.py", "monitor_router")
        fields  = mon_mod.MonitorStatusResponse.model_fields
        assert "sources"          in fields, "sources field missing from MonitorStatusResponse"
        assert "sources_healthy"  in fields, "sources_healthy missing"
        assert "sources_errored"  in fields, "sources_errored missing"
        assert "sources_integrated" in fields, "sources_integrated missing"

    def test_source_health_entry_has_required_fields(self):
        mon_mod = _load_module("backend/routers/monitor.py", "monitor_router")
        fields  = mon_mod.SourceHealthEntry.model_fields
        for f in ("source_id", "source_org", "province", "page_url",
                  "last_attempt", "last_ok", "last_error",
                  "alerts_contributed", "attempt_count"):
            assert f in fields, f"SourceHealthEntry missing field: {f}"

    def test_status_builds_from_state_file(self, tmp_path):
        """monitor_status() must correctly read source_health from state JSON."""
        import json
        state = {
            "seen_urls": ["url1", "url2"],
            "last_run": "2026-09-14T06:00:00Z",
            "source_health": {
                "ndma_advisories|https://ndma.gov.pk/advisories/": {
                    "source_id":          "ndma_advisories",
                    "source_org":         "NDMA",
                    "province":           "Pakistan",
                    "page_url":           "https://ndma.gov.pk/advisories/",
                    "last_attempt":       "2026-09-14T06:00:00Z",
                    "last_ok":            "2026-09-14T06:00:00Z",
                    "last_error":         None,
                    "alerts_contributed": 3,
                    "count":              5,
                },
                "pdma_punjab|https://pdma.punjab.gov.pk/": {
                    "source_id":          "pdma_punjab",
                    "source_org":         "PDMA Punjab",
                    "province":           "Punjab",
                    "page_url":           "https://pdma.punjab.gov.pk/",
                    "last_attempt":       "2026-09-14T06:00:00Z",
                    "last_ok":            None,
                    "last_error":         "HTTP 503",
                    "alerts_contributed": 0,
                    "count":              2,
                },
            },
        }
        sf = tmp_path / "alert_monitor_state.json"
        sf.write_text(json.dumps(state), encoding="utf-8")

        mon_mod = _load_module("backend/routers/monitor.py", "monitor_router")
        with patch.object(mon_mod, "_STATE_FILE", sf):
            with patch.object(mon_mod, "get_scheduler_status",
                              return_value={"running": True, "next_run": None}):
                resp = mon_mod.monitor_status()

        assert resp.seen_url_count == 2
        assert resp.sources_integrated == 2
        assert resp.sources_healthy == 1    # only NDMA has last_ok
        assert resp.sources_errored  == 1   # PDMA Punjab has last_error
        assert len(resp.sources)    == 2
        ndma_entry = next(s for s in resp.sources if s.source_id == "ndma_advisories")
        assert ndma_entry.alerts_contributed == 3
        assert ndma_entry.last_error is None
        punjab_entry = next(s for s in resp.sources if s.source_id == "pdma_punjab")
        assert punjab_entry.last_error == "HTTP 503"
        assert punjab_entry.last_ok is None


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2.3 — Location / radius filter on GET /alerts
# ══════════════════════════════════════════════════════════════════════════════

import os
os.environ.setdefault("ENV", "test")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from backend.database import Base, get_db
    from backend.main import app

    engine   = create_async_engine("sqlite+aiosqlite:///:memory:",
                                    connect_args={"check_same_thread": False})
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession,
        expire_on_commit=False, autoflush=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.anyio
async def test_radius_filter_returns_nearby_alerts(client):
    """Alerts within radius returned; alerts far away excluded."""
    admin_key = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")
    # Chitral city: 35.85, 71.78
    # Create one alert AT Chitral (distance = 0 km)
    r1 = await client.post("/alerts", json={
        "title": "Nearby Chitral Alert",
        "body":  "Flash flood in Chitral River basin.",
        "hazard_type": "flash_flood",
        "severity": "HIGH",
        "issued_at": "2026-09-14T06:00:00Z",
        "source_org": "NDMA",
        "district": "Chitral",
        "province": "Khyber Pakhtunkhwa",
        "latitude": 35.85,
        "longitude": 71.78,
        "language": "en",
        "verification_status": "PUBLISHED",
    }, headers={"X-Admin-Key": admin_key})
    assert r1.status_code == 201, r1.text

    # Create one alert FAR from Chitral (Karachi: 24.86, 67.01 — ~1700 km away)
    r2 = await client.post("/alerts", json={
        "title": "Karachi Alert",
        "body":  "Flood warning in Karachi coastal areas.",
        "hazard_type": "flood",
        "severity": "MEDIUM",
        "issued_at": "2026-09-14T06:00:00Z",
        "source_org": "PDMA Sindh",
        "district": "Karachi",
        "province": "Sindh",
        "latitude": 24.86,
        "longitude": 67.01,
        "language": "en",
        "verification_status": "PUBLISHED",
    }, headers={"X-Admin-Key": admin_key})
    assert r2.status_code == 201, r2.text

    # Radius query centred on Chitral with 100 km radius
    resp = await client.get(
        "/alerts?lat=35.85&lon=71.78&radius_km=100&active_only=true"
    )
    assert resp.status_code == 200
    data = resp.json()

    titles = [a["title"] for a in data["alerts"]]
    assert any("Chitral" in t for t in titles), "Nearby Chitral alert missing"
    assert not any("Karachi" in t for t in titles), "Karachi alert should be excluded"


@pytest.mark.anyio
async def test_location_match_type_coordinate(client):
    """Alerts with lat/lon matched by radius get location_match_type='coordinate'."""
    admin_key = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")
    await client.post("/alerts", json={
        "title": "Coordinate Match Alert",
        "body": "Flood advisory for Chitral.",
        "hazard_type": "flood", "severity": "HIGH",
        "issued_at": "2026-09-14T06:00:00Z",
        "source_org": "NDMA", "district": "Chitral",
        "province": "Khyber Pakhtunkhwa",
        "latitude": 35.85, "longitude": 71.78,
        "language": "en", "verification_status": "PUBLISHED",
    }, headers={"X-Admin-Key": admin_key})

    resp = await client.get("/alerts?lat=35.85&lon=71.78&radius_km=10")
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]
    coord_alerts = [a for a in alerts if a.get("location_match_type") == "coordinate"]
    assert len(coord_alerts) >= 1, "Expected at least one coordinate-matched alert"


@pytest.mark.anyio
async def test_national_alerts_always_shown_in_radius_query(client):
    """Alerts with district='Pakistan' appear in any radius query."""
    admin_key = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")
    await client.post("/alerts", json={
        "title": "National NDMA Advisory",
        "body":  "Pakistan-wide monsoon advisory from NDMA.",
        "hazard_type": "flood", "severity": "MEDIUM",
        "issued_at": "2026-09-14T06:00:00Z",
        "source_org": "NDMA", "district": "Pakistan",
        "province": "Pakistan", "language": "en",
        "verification_status": "PUBLISHED",
        # No lat/lon — national scope
    }, headers={"X-Admin-Key": admin_key})

    resp = await client.get("/alerts?lat=35.85&lon=71.78&radius_km=100")
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]
    national = [a for a in alerts if a.get("location_match_type") == "national"]
    assert len(national) >= 1, "National alert missing from radius query results"


@pytest.mark.anyio
async def test_province_filter_returns_correct_alerts(client):
    """?province=Punjab returns Punjab alerts; KP alerts excluded."""
    admin_key = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")
    for prov, dist in [("Punjab", "Lahore"), ("Khyber Pakhtunkhwa", "Chitral")]:
        await client.post("/alerts", json={
            "title": f"Alert for {dist}",
            "body":  f"Advisory for {prov}.",
            "hazard_type": "flood", "severity": "LOW",
            "issued_at": "2026-09-14T06:00:00Z",
            "source_org": "NDMA", "district": dist,
            "province": prov, "language": "en",
            "verification_status": "PUBLISHED",
        }, headers={"X-Admin-Key": admin_key})

    resp = await client.get("/alerts?province=Punjab")
    assert resp.status_code == 200
    titles = [a["title"] for a in resp.json()["alerts"]]
    assert any("Lahore" in t for t in titles), "Punjab alert missing"
    assert not any("Chitral" in t for t in titles), "KP alert should not appear in Punjab filter"


@pytest.mark.anyio
async def test_empty_radius_query_no_error(client):
    """Radius query with no matching alerts returns 200 with total=0 or >=0, not error."""
    # Query in middle of Indian Ocean — no alerts will be near there
    resp = await client.get("/alerts?lat=-20.0&lon=70.0&radius_km=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert data["total"] >= 0   # may be 0 or national alerts; not an error


@pytest.mark.anyio
async def test_haversine_distance_calculation():
    """Haversine function gives correct distances for known city pairs."""
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from routers.alerts import _haversine_km

    # Chitral to Islamabad: ~263 km (verified)
    d = _haversine_km(35.85, 71.78, 33.72, 73.04)
    assert 220 < d < 320, f"Chitral–Islamabad: expected ~263 km, got {d:.1f}"

    # Same point: 0 km
    assert _haversine_km(35.85, 71.78, 35.85, 71.78) < 0.001

    # Chitral to Karachi: > 1000 km
    d2 = _haversine_km(35.85, 71.78, 24.86, 67.01)
    assert d2 > 1000, f"Chitral–Karachi: expected >1000 km, got {d2:.1f}"
