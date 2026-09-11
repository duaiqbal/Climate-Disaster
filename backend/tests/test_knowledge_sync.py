"""
backend/tests/test_knowledge_sync.py
======================================
Tests for /knowledge and /sync endpoints.
"""

import pytest
from httpx import AsyncClient

ADMIN_KEY = "disaster-dss-dev-key-change-in-prod"


# ── Knowledge endpoints ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_knowledge_search_returns_200_or_503(client: AsyncClient):
    """
    /knowledge/search either returns results (200) if knowledge.sqlite exists,
    or 503 if it doesn't. Both are acceptable — we just must not crash.
    """
    resp = await client.get("/knowledge/search?q=flood&language=en")
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
async def test_knowledge_search_200_shape(client: AsyncClient):
    """If knowledge.sqlite exists, verify response shape."""
    resp = await client.get("/knowledge/search?q=flood&language=en&limit=5")
    if resp.status_code == 503:
        pytest.skip("knowledge.sqlite not available in test environment")
    data = resp.json()
    assert "query" in data
    assert "results" in data
    assert "total" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_knowledge_search_query_too_short(client: AsyncClient):
    """Query shorter than min_length=2 must return 422."""
    resp = await client.get("/knowledge/search?q=a&language=en")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_knowledge_chunks_200_or_503(client: AsyncClient):
    resp = await client.get("/knowledge/chunks?language=en&limit=5")
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
async def test_knowledge_meta_200_or_503(client: AsyncClient):
    resp = await client.get("/knowledge/meta")
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert "meta" in resp.json()


@pytest.mark.asyncio
async def test_knowledge_search_urdu(client: AsyncClient):
    """Urdu language param must be accepted without error."""
    resp = await client.get("/knowledge/search?q=flood&language=ur")
    assert resp.status_code in (200, 503)


@pytest.mark.asyncio
async def test_knowledge_search_roman_urdu(client: AsyncClient):
    resp = await client.get("/knowledge/search?q=flood+mein&language=ru")
    assert resp.status_code in (200, 503)


# ── Sync endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_status_empty(client: AsyncClient):
    """No packages published yet — status should be null."""
    resp = await client.get("/sync/status")
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_sync_publish_requires_admin(client: AsyncClient):
    resp = await client.post("/sync/publish", json={
        "version": "1.0.0",
        "built_at": "2024-08-01T00:00:00",
        "chunk_count": 315,
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sync_publish_success(client: AsyncClient):
    resp = await client.post("/sync/publish", json={
        "version": "1.0.0",
        "built_at": "2024-08-01T00:00:00",
        "chunk_count": 315,
        "knowledge_checksum": "abc123",
        "hazard_checksum": "def456",
        "release_notes": "Test release",
    }, headers={"X-Admin-Key": ADMIN_KEY})
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == "1.0.0"
    assert data["chunk_count"] == 315


@pytest.mark.asyncio
async def test_sync_status_after_publish(client: AsyncClient):
    await client.post("/sync/publish", json={
        "version": "2.0.0",
        "built_at": "2024-09-01T00:00:00",
        "chunk_count": 400,
    }, headers={"X-Admin-Key": ADMIN_KEY})

    resp = await client.get("/sync/status")
    assert resp.status_code == 200
    assert resp.json()["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_sync_updates_list(client: AsyncClient):
    for i in range(3):
        await client.post("/sync/publish", json={
            "version": f"1.{i}.0",
            "built_at": f"2024-0{i+1}-01T00:00:00",
            "chunk_count": 100 + i,
        }, headers={"X-Admin-Key": ADMIN_KEY})

    resp = await client.get("/sync/updates")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ── RAG endpoint ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rag_query_empty_question(client: AsyncClient):
    resp = await client.post("/rag/query", json={"question": "", "language": "en"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rag_query_insufficient_evidence_when_no_db(client: AsyncClient):
    """
    When knowledge.sqlite is absent (503) or returns no chunks,
    the RAG layer must return 'insufficient' confidence — never fabricate.
    """
    resp = await client.post("/rag/query", json={
        "question": "What should I do during a flood?",
        "language": "en",
    })
    # Either 200 (knowledge DB present) or 503 (DB absent)
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        data = resp.json()
        assert "answer" in data
        assert "confidence" in data
        assert "sources" in data
        assert data["confidence"] in ("sufficient", "insufficient", "no_llm")
        # Verify constraint 5: low confidence → insufficient evidence message
        if data["confidence"] == "insufficient":
            assert "INSUFFICIENT EVIDENCE" in data["answer"]


@pytest.mark.asyncio
async def test_rag_response_shape(client: AsyncClient):
    resp = await client.post("/rag/query", json={
        "question": "flood safety tips",
        "language": "en",
        "top_k": 3,
    })
    if resp.status_code == 503:
        pytest.skip("knowledge.sqlite not available")
    data = resp.json()
    # All required fields present
    for field in ["question", "answer", "confidence", "provider_used",
                  "generation_used", "retrieval_score", "sources", "disclaimer"]:
        assert field in data, f"Missing field: {field}"
