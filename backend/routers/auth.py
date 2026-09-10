"""
backend/routers/auth.py
========================
User registration and login endpoints.

POST /auth/register   — create a new user account
POST /auth/login      — authenticate and receive a token

Token strategy: simple HMAC-SHA256 signed token (no JWT library dependency).
In production, replace with python-jose + OAuth2 bearer tokens.
"""

import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.db_models import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserORM,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "disaster-dss-dev-secret-change-in-production")
TOKEN_TTL = int(os.getenv("TOKEN_TTL_SECONDS", "86400"))  # 24 h


# ── Password hashing (PBKDF2-HMAC-SHA256) ────────────────────────────────────
def _hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}:{dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, dk_hex = stored.split(":", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ── Token creation/verification ───────────────────────────────────────────────
def _create_token(user_id: int, email: str) -> str:
    payload = json.dumps({"uid": user_id, "email": email, "exp": int(time.time()) + TOKEN_TTL})
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    import base64
    b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{b64}.{sig}"


def _decode_token(token: str) -> Optional[dict]:
    try:
        import base64
        b64, sig = token.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(b64 + "==").decode()
        expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(payload)
        if data["exp"] < int(time.time()):
            return None
        return data
    except Exception:
        return None


# ── Register ──────────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserResponse,
             status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check email uniqueness
    result = await db.execute(
        select(UserORM).where(UserORM.email == payload.email.lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = UserORM(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        hashed_password=_hash_password(payload.password),
        district=payload.district,
        language=payload.language,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)


# ── Login ─────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserORM).where(UserORM.email == payload.email.lower())
    )
    user = result.scalar_one_or_none()

    if not user or not _verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    token = _create_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
