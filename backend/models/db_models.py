"""
backend/models/db_models.py
============================
SQLAlchemy ORM models + Pydantic request/response schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


# ══════════════════════════════════════════════════════════════════════════════
# ORM Models
# ══════════════════════════════════════════════════════════════════════════════


class AlertORM(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False,
                                           default=lambda: str(uuid.uuid4())[:8])
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    hazard_type: Mapped[str] = mapped_column(String(32), nullable=False)  # flood, landslide …
    severity: Mapped[str] = mapped_column(String(16), nullable=False)     # LOW/MEDIUM/HIGH/EXTREME
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_org: Mapped[str] = mapped_column(String(64), nullable=False)   # NDMA / PDMA KP / PMD
    district: Mapped[str] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    district: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PackageUpdateORM(Base):
    """Records each time an offline package build is published."""
    __tablename__ = "package_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    knowledge_checksum: Mapped[str] = mapped_column(String(64), nullable=True)
    hazard_checksum: Mapped[str] = mapped_column(String(64), nullable=True)
    release_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ══════════════════════════════════════════════════════════════════════════════

VALID_HAZARD_TYPES = {"flood", "flash_flood", "landslide", "glof", "other"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "EXTREME"}
VALID_LANGUAGES = {"en", "ur", "ru"}


class AlertCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    body: str = Field(..., min_length=10)
    hazard_type: str = Field(..., description="flood|flash_flood|landslide|glof|other")
    severity: str = Field(..., description="LOW|MEDIUM|HIGH|EXTREME")
    issued_at: datetime
    source_org: str = Field(..., min_length=2, max_length=64)
    district: Optional[str] = Field(None, max_length=64)
    language: str = Field("en", description="en|ur|ru")

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


class AlertResponse(BaseModel):
    alert_id: str
    title: str
    body: str
    hazard_type: str
    severity: str
    issued_at: datetime
    source_org: str
    district: Optional[str]
    language: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    total: int
    alerts: list[AlertResponse]


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=4, max_length=128)
    district: Optional[str] = Field(None, max_length=64)
    language: str = Field("en")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {VALID_LANGUAGES}")
        return v


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    district: Optional[str]
    language: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PackageUpdateResponse(BaseModel):
    version: str
    built_at: datetime
    chunk_count: int
    knowledge_checksum: Optional[str]
    hazard_checksum: Optional[str]
    release_notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    timestamp: datetime
