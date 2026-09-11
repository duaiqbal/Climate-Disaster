"""
backend/tests/test_auth.py
============================
Comprehensive authentication tests covering every scenario from the spec:

  ✓ registration
  ✓ duplicate registration
  ✓ valid login
  ✓ invalid password
  ✓ invalid user
  ✓ token refresh
  ✓ revoked refresh token
  ✓ unauthorized endpoint access
  ✓ logout / session invalidation
  ✓ /auth/me with valid token
  ✓ /auth/me with expired/invalid token
  ✓ password minimum length enforcement
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ── Helpers ───────────────────────────────────────────────────────────────────

async def register_user(client: AsyncClient, email: str, password: str = "ValidPass123",
                        name: str = "Test User") -> dict:
    resp = await client.post("/auth/register", json={
        "name": name, "email": email, "password": password, "language": "en"
    })
    return resp


async def login_user(client: AsyncClient, email: str,
                     password: str = "ValidPass123") -> dict:
    resp = await client.post("/auth/login", json={
        "email": email, "password": password
    })
    return resp


# ── Registration tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await register_user(client, "newuser@test.com")
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@test.com"
    assert "id" in data
    assert "hashed_password" not in data  # never expose hash


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await register_user(client, "dup@test.com")
    resp = await register_user(client, "dup@test.com")
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "name": "Test", "email": "short@test.com",
        "password": "1234567",  # 7 chars — below min of 8
        "language": "en"
    })
    assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_register_password_minimum_8_chars(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "name": "Test", "email": "min8@test.com",
        "password": "12345678",  # exactly 8 chars — should pass
        "language": "en"
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "name": "Test", "email": "not-an-email",
        "password": "ValidPass123", "language": "en"
    })
    assert resp.status_code == 422


# ── Login tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_valid(client: AsyncClient):
    await register_user(client, "login@test.com")
    resp = await login_user(client, "login@test.com")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data
    assert "user" in data
    assert data["user"]["email"] == "login@test.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await register_user(client, "wrongpass@test.com")
    resp = await login_user(client, "wrongpass@test.com", password="WrongPass999")
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await login_user(client, "nobody@test.com")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_case_insensitive_email(client: AsyncClient):
    await register_user(client, "CaseTest@test.com")
    resp = await login_user(client, "CASETEST@TEST.COM")
    assert resp.status_code == 200


# ── Token tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_with_valid_token(client: AsyncClient):
    await register_user(client, "me@test.com")
    login_resp = await login_user(client, "me@test.com")
    token = login_resp.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.com"


@pytest.mark.asyncio
async def test_get_me_without_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_invalid_token(client: AsyncClient):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_malformed_header(client: AsyncClient):
    resp = await client.get("/auth/me", headers={"Authorization": "NotBearer token"})
    assert resp.status_code == 401


# ── Refresh token tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient):
    await register_user(client, "refresh@test.com")
    login_resp = await login_user(client, "refresh@test.com")
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token must differ from old one (rotation)
    assert data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_token_rotation_invalidates_old(client: AsyncClient):
    """After rotation, the old refresh token must be revoked."""
    await register_user(client, "rotate@test.com")
    login_resp = await login_user(client, "rotate@test.com")
    old_refresh = login_resp.json()["refresh_token"]

    # Use old token once — triggers rotation
    await client.post("/auth/refresh", json={"refresh_token": old_refresh})

    # Try to use the old token again — must be rejected
    resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    resp = await client.post("/auth/refresh", json={"refresh_token": "completely-invalid-token"})
    assert resp.status_code == 401


# ── Logout tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient):
    await register_user(client, "logout@test.com")
    login_resp = await login_user(client, "logout@test.com")
    refresh_token = login_resp.json()["refresh_token"]

    # Logout revokes the refresh token
    logout_resp = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204

    # Refresh must now fail
    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalid_token_still_204(client: AsyncClient):
    """Logout with an invalid token must return 204 — never reveal token existence."""
    resp = await client.post("/auth/logout", json={"refresh_token": "nonexistent-token"})
    assert resp.status_code == 204


# ── Admin authorization tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_alert_without_admin_key_rejected(client: AsyncClient):
    """Alert creation requires X-Admin-Key — unauthenticated must get 403."""
    from datetime import datetime, timezone
    resp = await client.post("/alerts", json={
        "title": "Test Alert Title Here",
        "body": "Test body content here that is long enough",
        "hazard_type": "flood",
        "severity": "HIGH",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "source_org": "NDMA",
        "language": "en",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_health_endpoint_public(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
