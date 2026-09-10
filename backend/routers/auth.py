"""
backend/routers/auth.py
========================
Production-quality authentication endpoints.

POST /auth/register      — create account (bcrypt password)
POST /auth/login         — login → JWT access + opaque refresh token
POST /auth/refresh        — exchange refresh token for new access token
POST /auth/logout         — revoke refresh token
GET  /auth/me             — get current user (requires valid access token)

Security:
  - bcrypt password hashing (via passlib)
  - JWT access tokens (python-jose, HS256, configurable TTL)
  - Opaque refresh tokens stored as SHA-256 hashes in DB
  - Refresh token rotation: each refresh issues a new token, old one revoked
  - Brute-force protection: rate limiting via slowapi
  - No default/hardcoded credentials
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.security import (
    create_access_token,
    generate_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
)
from backend.database import get_db
from backend.models.db_models import (
    LoginRequest,
    RefreshRequest,
    RefreshTokenORM,
    TokenResponse,
    UserCreate,
    UserORM,
    UserResponse,
)

router  = APIRouter(prefix="/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


def _hash_refresh_token(token: str) -> str:
    """Store only the hash of the refresh token, never the plaintext."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── Register ──────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserResponse,
             status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account with bcrypt-hashed password."""
    existing = await db.execute(
        select(UserORM).where(UserORM.email == payload.email.lower().strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = UserORM(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        role="user",
        district=payload.district,
        language=payload.language,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and return JWT access token + opaque refresh token."""
    result = await db.execute(
        select(UserORM).where(UserORM.email == payload.email.lower().strip())
    )
    user = result.scalar_one_or_none()

    # Constant-time comparison to prevent timing attacks on email enumeration
    if not user:
        # Still call verify to avoid timing difference revealing email existence
        verify_password("dummy", "$2b$12$dummy.hash.to.prevent.timing.attack.here")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    # Issue access token
    access_token = create_access_token(user.id, user.email, user.role)

    # Issue refresh token (stored as hash)
    refresh_plain = generate_refresh_token()
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_token_ttl)
    db.add(RefreshTokenORM(
        user_id=user.id,
        token_hash=_hash_refresh_token(refresh_plain),
        expires_at=expires,
        user_agent=request.headers.get("User-Agent", "")[:255],
        ip_address=request.client.host if request.client else None,
    ))
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_plain,
        token_type="bearer",
        expires_in=settings.access_token_ttl,
        user=UserResponse.model_validate(user),
    )


# ── Refresh ───────────────────────────────────────────────────────────────────
@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    Implements refresh token rotation: old token is revoked, new one issued.
    """
    token_hash = _hash_refresh_token(payload.refresh_token)

    result = await db.execute(
        select(RefreshTokenORM).where(RefreshTokenORM.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()

    if not stored or stored.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token.",
        )

    if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
        )

    # Revoke old token (rotation)
    stored.revoked = True
    stored.revoked_at = datetime.now(timezone.utc)

    # Load user
    user_result = await db.execute(
        select(UserORM).where(UserORM.id == stored.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User not found or deactivated.")

    # Issue new tokens
    access_token = create_access_token(user.id, user.email, user.role)
    new_refresh = generate_refresh_token()
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_token_ttl)
    db.add(RefreshTokenORM(
        user_id=user.id,
        token_hash=_hash_refresh_token(new_refresh),
        expires_at=expires,
        user_agent=request.headers.get("User-Agent", "")[:255],
        ip_address=request.client.host if request.client else None,
    ))
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.access_token_ttl,
        user=UserResponse.model_validate(user),
    )


# ── Logout ────────────────────────────────────────────────────────────────────
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Revoke a refresh token. Access token expires naturally via TTL."""
    token_hash = _hash_refresh_token(payload.refresh_token)
    result = await db.execute(
        select(RefreshTokenORM).where(RefreshTokenORM.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()
    if stored and not stored.revoked:
        stored.revoked = True
        stored.revoked_at = datetime.now(timezone.utc)
        await db.flush()
    # Always return 204 — don't reveal if token existed


# ── Current user ──────────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def get_me(user: UserORM = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(user)
