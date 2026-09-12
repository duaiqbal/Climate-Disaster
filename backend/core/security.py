"""
backend/core/security.py
=========================
Authentication utilities using direct bcrypt (no passlib wrapper).
- bcrypt password hashing
- JWT access tokens (python-jose)
- Refresh token generation
- get_current_user FastAPI dependency
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from database import get_db

# ── Password hashing (direct bcrypt, no passlib) ──────────────────────────────
_BCRYPT_ROUNDS = 12

# Pre-computed dummy hash used for timing-safe login (prevents email enumeration)
_DUMMY_HASH: str = bcrypt.hashpw(
    b"__dummy_password_for_timing_safety__",
    bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
).decode("utf-8")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash. Always returns bool."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT access tokens ─────────────────────────────────────────────────────────
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def create_access_token(user_id: int, email: str, role: str = "user") -> str:
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.access_token_ttl)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── Refresh tokens ────────────────────────────────────────────────────────────

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise exc

    payload = decode_access_token(token)
    if not payload:
        raise exc

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise exc

    from models.db_models import UserORM
    result = await db.execute(select(UserORM).where(UserORM.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise exc
    return user


async def get_current_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin role required.")
    return user
