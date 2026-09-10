"""
backend/models/db_models.py
============================
SQLAlchemy ORM models + Pydantic request/response schemas.

ORM tables:
  users            — registered users with role
  refresh_tokens   — refresh token store for revocation
  alerts           — official disaster alerts with full provenance
  package_updates  — offline package version history
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


# ══════════════════════════════════════════════════════════════════════════════
# ORM Models
# ══════════════════════════════════════════════════════════════════════════════

class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str]        = mapped_column(String(120), nullable=False)
    email: Mapped[str]       = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str]        = mapped_column(String(16), nullable=False, default="user")
    district: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[str]    = mapped_column(String(8), default="en")
    is_active: Mapped[bool]  = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RefreshTokenORM(Base):
    """
    Opaque refresh token store.
    One row per issued refresh token — allows selective revocation.
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int]     = mapped_column(Integer, nullable=False, index=True)
    token_hash: Mapped[str]  = mapped_column(String(128), unique=True, nullable=False)
    issued_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool]    = mapped_column(Boolean, default=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class AlertORM(Base):
    """
    Official disaster alert with full provenance (constraint 4).

    Every alert MUST carry:
      source_org         — publishing organisation
      source_url         — original URL of the official source
      fetch_timestamp    — when this system fetched it
      content_hash       — SHA-256 of body for change detection
      verification_status — DISCOVERED/FETCHED/VALIDATED/OFFICIAL-VERIFIED/PUBLISHED
    """
    __tablename__ = "alerts"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str]    = mapped_column(String(64), unique=True, nullable=False,
                                              default=lambda: str(uuid.uuid4())[:12])
    title: Mapped[str]       = mapped_column(String(255), nullable=False)
    body: Mapped[str]        = mapped_column(Text, nullable=False)
    hazard_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str]    = mapped_column(String(16), nullable=False)

    # Temporal fields
    issued_at: Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False)
    fetch_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]]      = mapped_column(DateTime(timezone=True), nullable=True)

    # Provenance — REQUIRED per hard constraint 4
    source_org: Mapped[str]         = mapped_column(String(64), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Lifecycle state
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DISCOVERED"
    )
    # Lifecycle: DISCOVERED → FETCHED → VALIDATED → OFFICIAL-VERIFIED → PUBLISHED → EXPIRED

    # Geographic
    district: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Content
    language: Mapped[str]    = mapped_column(String(8), default="en")
    is_active: Mapped[bool]  = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_alerts_district",  "district"),
        Index("ix_alerts_hazard",    "hazard_type"),
        Index("ix_alerts_issued_at", "issued_at"),
        Index("ix_alerts_status",    "verification_status"),
    )


class PackageUpdateORM(Base):
    __tablename__ = "package_updates"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str]     = mapped_column(String(32), nullable=False)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    knowledge_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hazard_checksum: Mapped[Optional[str]]    = mapped_column(String(64), nullable=True)
    release_notes: Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ══════════════════════════════════════════════════════════════════════════════

VALID_HAZARD_TYPES = {"flood", "flash_flood", "landslide", "glof", "other", "general"}
VALID_SEVERITIES   = {"LOW", "MEDIUM", "HIGH", "EXTREME"}
VALID_LANGUAGES    = {"en", "ur", "ru"}
VALID_ROLES        = {"user", "admin"}
VALID_ALERT_STATES = {
    "DISCOVERED", "FETCHED", "VALIDATED", "OFFICIAL-VERIFIED", "PUBLISHED", "EXPIRED"
}


# ── User schemas ───────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name:     str = Field(..., min_length=2, max_length=120)
    email:    str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=8, max_length=128)  # min 8, up from 4
    district: Optional[str] = Field(None, max_length=64)
    language: str = Field("en")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {VALID_LANGUAGES}")
        return v


class UserResponse(BaseModel):
    id:        int
    name:      str
    email:     str
    role:      str
    district:  Optional[str]
    language:  str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email:    str
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int  # seconds
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Alert schemas ──────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    title:       str = Field(..., min_length=5, max_length=255)
    body:        str = Field(..., min_length=10)
    hazard_type: str
    severity:    str
    issued_at:   datetime
    source_org:  str = Field(..., min_length=2, max_length=64)
    source_url:  Optional[str] = Field(None, max_length=512)
    district:    Optional[str] = Field(None, max_length=64)
    province:    Optional[str] = Field(None, max_length=64)
    language:    str = Field("en")
    verification_status: str = Field("OFFICIAL-VERIFIED")

    @field_validator("hazard_type")
    @classmethod
    def validate_hazard_type(cls, v: str) -> str:
        v = v.lower()
        if v not in VALID_HAZARD_TYPES:
            raise ValueError(f"hazard_type must be one of {VALID_HAZARD_TYPES}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        v = v.upper()
        if v not in VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {VALID_SEVERITIES}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {VALID_LANGUAGES}")
        return v

    @field_validator("verification_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v = v.upper().replace(" ", "-")
        if v not in VALID_ALERT_STATES:
            raise ValueError(f"verification_status must be one of {VALID_ALERT_STATES}")
        return v


class AlertResponse(BaseModel):
    alert_id:            str
    title:               str
    body:                str
    hazard_type:         str
    severity:            str
    issued_at:           datetime
    fetch_timestamp:     Optional[datetime]
    source_org:          str
    source_url:          Optional[str]
    verification_status: str
    district:            Optional[str]
    province:            Optional[str]
    language:            str
    is_active:           bool
    created_at:          datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    total:  int
    alerts: list[AlertResponse]


# ── Package update schemas ─────────────────────────────────────────────────────

class PackageUpdateResponse(BaseModel):
    version:            str
    built_at:           datetime
    chunk_count:        int
    knowledge_checksum: Optional[str]
    hazard_checksum:    Optional[str]
    release_notes:      Optional[str]
    created_at:         datetime

    model_config = {"from_attributes": True}


# ── Health schema ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:    str
    version:   str
    db:        str
    env:       str
    timestamp: datetime
