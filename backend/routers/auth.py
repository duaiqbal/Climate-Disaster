"""
backend/routers/auth.py
========================
Production authentication: bcrypt + JWT + refresh token rotation.

POST /auth/register  — create account
POST /auth/login     — login → JWT access + opaque refresh token
POST /auth/refresh   — rotate refresh token → new access token
POST /auth/logout    — revoke refresh token
GET  /auth/me        — current user profile (requires valid JWT)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.security import (
    _DUMMY_HASH,
    create_access_token,
    generate_refresh_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
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

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Register ──────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserResponse,
             status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(UserORM).where(UserORM.email == payload.email.lower().strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409,
                            detail="An account with this email already exists.")

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
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserORM).where(UserORM.email == payload.email.lower().strip())
    )
    user = result.scalar_one_or_none()

    if not user:
        # Timing-safe: always call verify to prevent email enumeration
        verify_password("dummy", _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated.")

    access_token   = create_access_token(user.id, user.email, user.role)
    refresh_plain  = generate_refresh_token()
    expires        = datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_token_ttl)

    db.add(RefreshTokenORM(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_plain),
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
    stored_hash = hash_refresh_token(payload.refresh_token)
    result = await db.execute(
        select(RefreshTokenORM).where(RefreshTokenORM.token_hash == stored_hash)
    )
    stored = result.scalar_one_or_none()

    if not stored or stored.revoked:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token.")

    if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token has expired. Please log in again.")

    # Rotate — revoke old token
    stored.revoked    = True
    stored.revoked_at = datetime.now(timezone.utc)

    user_result = await db.execute(select(UserORM).where(UserORM.id == stored.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated.")

    access_token  = create_access_token(user.id, user.email, user.role)
    new_refresh   = generate_refresh_token()
    expires       = datetime.now(timezone.utc) + timedelta(seconds=settings.refresh_token_ttl)

    db.add(RefreshTokenORM(
        user_id=user.id,
        token_hash=hash_refresh_token(new_refresh),
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
@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    stored_hash = hash_refresh_token(payload.refresh_token)
    result = await db.execute(
        select(RefreshTokenORM).where(RefreshTokenORM.token_hash == stored_hash)
    )
    stored = result.scalar_one_or_none()
    if stored and not stored.revoked:
        stored.revoked    = True
        stored.revoked_at = datetime.now(timezone.utc)
        await db.flush()
    # Always 204 — never reveal whether token existed


# ── Current user ──────────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def get_me(user: UserORM = Depends(get_current_user)):
    return UserResponse.model_validate(user)
