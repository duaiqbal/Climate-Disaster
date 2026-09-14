"""
backend/models/db_models.py
============================
SQLAlchemy ORM models (SQLite default, PostgreSQL compatible).

Tables:
  users             — registered users with role
  refresh_tokens    — refresh token store for JWT rotation
  sources           — official data sources (org, url, checksum, fetch time)
  ingestion_runs    — audit log of every ingestion job execution
  alerts            — official disaster alerts with full provenance
  alert_history     — immutable audit trail of every alert state change
  package_updates   — offline package version history

Provenance chain:
  sources ──► alerts (source_id FK)
  ingestion_runs ──► alerts (ingestion_run_id FK)
  alerts ──► alert_history (alert_id FK)

Design principles:
  - All FKs are explicit SQLAlchemy ForeignKey() — enforced by PostgreSQL,
    advisory in SQLite.
  - No SQLite-specific SQL anywhere; all queries use SQLAlchemy ORM.
  - Indexes on location, hazard_type, published_at, verification_status.
  - DATABASE_URL swap to postgresql+asyncpg:// requires zero code changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ══════════════════════════════════════════════════════════════════════════════
# ORM Models
# ══════════════════════════════════════════════════════════════════════════════

class UserORM(Base):
    __tablename__ = "users"

    id:              Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:            Mapped[str]           = mapped_column(String(120), nullable=False)
    email:           Mapped[str]           = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str]           = mapped_column(String(255), nullable=False)
    role:            Mapped[str]           = mapped_column(String(16), nullable=False, default="user")
    district:        Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language:        Mapped[str]           = mapped_column(String(8), default="en")
    is_active:       Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_role",  "role"),
    )


class RefreshTokenORM(Base):
    """Opaque refresh token store — one row per issued token for revocation."""
    __tablename__ = "refresh_tokens"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:     Mapped[int]           = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash:  Mapped[str]           = mapped_column(String(128), unique=True, nullable=False)
    issued_at:   Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at:  Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False)
    revoked:     Mapped[bool]          = mapped_column(Boolean, default=False)
    revoked_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent:  Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address:  Mapped[Optional[str]] = mapped_column(String(64),  nullable=True)

    __table_args__ = (
        Index("ix_refresh_tokens_user_id",    "user_id"),
        Index("ix_refresh_tokens_token_hash", "token_hash"),
        Index("ix_refresh_tokens_revoked",    "revoked"),
    )


# ── NEW: SourceORM ─────────────────────────────────────────────────────────────

class SourceORM(Base):
    """
    Official data source registry.
    One row per unique URL/publication — alerts link back here for provenance.
    """
    __tablename__ = "sources"

    id:           Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id:    Mapped[str]           = mapped_column(String(64), unique=True, nullable=False,
                                                         default=lambda: str(uuid.uuid4())[:12])
    org:          Mapped[str]           = mapped_column(String(64), nullable=False)   # NDMA / PDMA KP / PMD
    doc_title:    Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url:   Mapped[str]           = mapped_column(String(512), nullable=False)
    fetched_at:   Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False,
                                                         server_default=func.now())
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)   # pdf / html / json
    language:     Mapped[str]           = mapped_column(String(8), default="en")
    is_active:    Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at:   Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    alerts: Mapped[list["AlertORM"]] = relationship("AlertORM", back_populates="source")

    __table_args__ = (
        Index("ix_sources_org",         "org"),
        Index("ix_sources_source_url",  "source_url"),
        Index("ix_sources_fetched_at",  "fetched_at"),
        Index("ix_sources_checksum",    "checksum_sha256"),
    )


# ── NEW: IngestionRunORM ───────────────────────────────────────────────────────

class IngestionRunORM(Base):
    """
    Audit log of every ingestion job execution.
    Records what was fetched, how many alerts were created/updated,
    and whether any errors occurred.
    """
    __tablename__ = "ingestion_runs"

    id:              Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id:          Mapped[str]           = mapped_column(String(64), unique=True, nullable=False,
                                                            default=lambda: str(uuid.uuid4())[:12])
    started_at:      Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False,
                                                            server_default=func.now())
    finished_at:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger:         Mapped[str]           = mapped_column(String(32), default="scheduled")
                                                            # scheduled | manual | api
    status:          Mapped[str]           = mapped_column(String(16), default="running")
                                                            # running | success | partial | failed
    sources_checked: Mapped[int]           = mapped_column(Integer, default=0)
    new_found:       Mapped[int]           = mapped_column(Integer, default=0)
    alerts_created:  Mapped[int]           = mapped_column(Integer, default=0)
    alerts_skipped:  Mapped[int]           = mapped_column(Integer, default=0)
    error_message:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    runner_version:  Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Relationships
    alerts: Mapped[list["AlertORM"]] = relationship("AlertORM", back_populates="ingestion_run")

    __table_args__ = (
        Index("ix_ingestion_runs_started_at", "started_at"),
        Index("ix_ingestion_runs_status",     "status"),
        Index("ix_ingestion_runs_trigger",    "trigger"),
    )


# ── EXTENDED: AlertORM ─────────────────────────────────────────────────────────

class AlertORM(Base):
    """
    Official disaster alert with full provenance (hard constraint 4).

    Provenance chain:
      source_id        → SourceORM (which org, which URL, which checksum)
      ingestion_run_id → IngestionRunORM (which job created this alert)

    Every alert must carry source_org, source_url, fetch_timestamp,
    content_hash, and verification_status — never nullable in practice.
    """
    __tablename__ = "alerts"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id:    Mapped[str]  = mapped_column(String(64), unique=True, nullable=False,
                                               default=lambda: str(uuid.uuid4())[:12])
    title:       Mapped[str]  = mapped_column(String(255), nullable=False)
    body:        Mapped[str]  = mapped_column(Text, nullable=False)
    hazard_type: Mapped[str]  = mapped_column(String(32), nullable=False)
    severity:    Mapped[str]  = mapped_column(String(16), nullable=False)

    # ── Temporal ───────────────────────────────────────────────────────────────
    issued_at:       Mapped[datetime]           = mapped_column(DateTime(timezone=True), nullable=False)
    published_at:    Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fetch_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Provenance (hard constraint 4) ─────────────────────────────────────────
    source_org:          Mapped[str]           = mapped_column(String(64), nullable=False)
    source_url:          Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content_hash:        Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str]           = mapped_column(String(32), nullable=False,
                                                                default="DISCOVERED")
    # FK to SourceORM — nullable so manual alerts without a tracked source are allowed
    source_id:           Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("sources.source_id", ondelete="SET NULL"), nullable=True
    )
    # FK to IngestionRunORM — nullable for manually created alerts
    ingestion_run_id:    Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("ingestion_runs.run_id", ondelete="SET NULL"), nullable=True
    )

    # ── Geographic ─────────────────────────────────────────────────────────────
    district:   Mapped[Optional[str]] = mapped_column(String(64),  nullable=True)
    province:   Mapped[Optional[str]] = mapped_column(String(64),  nullable=True)
    latitude:   Mapped[Optional[float]] = mapped_column(Float,     nullable=True)
    longitude:  Mapped[Optional[float]] = mapped_column(Float,     nullable=True)

    # ── Content ────────────────────────────────────────────────────────────────
    language:   Mapped[str]  = mapped_column(String(8), default="en")
    is_active:  Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ──────────────────────────────────────────────────────────
    source:         Mapped[Optional["SourceORM"]]        = relationship("SourceORM",        back_populates="alerts")
    ingestion_run:  Mapped[Optional["IngestionRunORM"]]  = relationship("IngestionRunORM",  back_populates="alerts")
    history:        Mapped[list["AlertHistoryORM"]]      = relationship("AlertHistoryORM",  back_populates="alert",
                                                                          cascade="all, delete-orphan",
                                                                          order_by="AlertHistoryORM.changed_at")

    __table_args__ = (
        # Frequently-queried columns — required by the spec
        Index("ix_alerts_district",             "district"),
        Index("ix_alerts_hazard_type",          "hazard_type"),
        Index("ix_alerts_published_at",         "published_at"),
        Index("ix_alerts_issued_at",            "issued_at"),
        Index("ix_alerts_verification_status",  "verification_status"),
        Index("ix_alerts_severity",             "severity"),
        Index("ix_alerts_source_id",            "source_id"),
        Index("ix_alerts_ingestion_run_id",     "ingestion_run_id"),
        # Composite index for the most common query pattern
        Index("ix_alerts_district_hazard",      "district", "hazard_type"),
    )


# ── NEW: AlertHistoryORM ──────────────────────────────────────────────────────

class AlertHistoryORM(Base):
    """
    Immutable audit trail of every alert state change.
    One row is appended every time an alert is modified or transitions lifecycle.
    Never updated, never deleted — append-only.
    """
    __tablename__ = "alert_history"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    # FK to the parent alert — cascade delete so history is removed with the alert
    alert_db_id: Mapped[int]  = mapped_column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    changed_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                   server_default=func.now())
    changed_by:  Mapped[Optional[str]] = mapped_column(String(64),  nullable=True)  # user email or "system"
    field_name:  Mapped[str]  = mapped_column(String(64),  nullable=False)   # e.g. "verification_status"
    old_value:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action:      Mapped[str]  = mapped_column(String(32), nullable=False)    # created | updated | transitioned | deleted

    # Relationship back to parent alert
    alert: Mapped["AlertORM"] = relationship("AlertORM", back_populates="history")

    __table_args__ = (
        Index("ix_alert_history_alert_db_id",  "alert_db_id"),
        Index("ix_alert_history_changed_at",   "changed_at"),
        Index("ix_alert_history_action",       "action"),
    )


class PackageUpdateORM(Base):
    __tablename__ = "package_updates"

    id:                 Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    version:            Mapped[str]           = mapped_column(String(32), nullable=False)
    built_at:           Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False)
    chunk_count:        Mapped[int]           = mapped_column(Integer, default=0)
    knowledge_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hazard_checksum:    Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    release_notes:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at:         Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_package_updates_version",   "version"),
        Index("ix_package_updates_built_at",  "built_at"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ══════════════════════════════════════════════════════════════════════════════

VALID_HAZARD_TYPES = {"flood", "flash_flood", "landslide", "glof", "other", "general"}
VALID_SEVERITIES   = {"LOW", "MEDIUM", "HIGH", "EXTREME"}
VALID_LANGUAGES    = {"en", "ur", "ru"}
VALID_ROLES        = {"user", "admin"}
VALID_ALERT_STATES = {
    "DISCOVERED", "FETCHED", "VALIDATED",
    "OFFICIAL-VERIFIED", "PUBLISHED", "EXPIRED",
}

# ── User schemas ───────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name:     str = Field(..., min_length=2, max_length=120)
    email:    str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=8, max_length=128)
    district: Optional[str] = Field(None, max_length=64)
    language: str = Field("en")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {VALID_LANGUAGES}")
        return v


class UserResponse(BaseModel):
    id:         int
    name:       str
    email:      str
    role:       str
    district:   Optional[str]
    language:   str
    is_active:  bool
    created_at: datetime
    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email:    str
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int
    user:          UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Source schemas ─────────────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    org:             str = Field(..., min_length=2, max_length=64)
    doc_title:       Optional[str] = Field(None, max_length=255)
    source_url:      str = Field(..., max_length=512)
    fetched_at:      Optional[datetime] = None
    checksum_sha256: Optional[str] = Field(None, max_length=64)
    content_type:    Optional[str] = Field(None, max_length=64)
    language:        str = Field("en")


class SourceResponse(BaseModel):
    source_id:       str
    org:             str
    doc_title:       Optional[str]
    source_url:      str
    fetched_at:      datetime
    checksum_sha256: Optional[str]
    content_type:    Optional[str]
    language:        str
    is_active:       bool
    created_at:      datetime
    model_config = {"from_attributes": True}


# ── IngestionRun schemas ───────────────────────────────────────────────────────

class IngestionRunResponse(BaseModel):
    run_id:          str
    started_at:      datetime
    finished_at:     Optional[datetime]
    trigger:         str
    status:          str
    sources_checked: int
    new_found:       int
    alerts_created:  int
    alerts_skipped:  int
    error_message:   Optional[str]
    model_config = {"from_attributes": True}


# ── Alert schemas ──────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    title:               str = Field(..., min_length=5, max_length=255)
    body:                str = Field(..., min_length=10)
    hazard_type:         str
    severity:            str
    issued_at:           datetime
    fetch_timestamp:     Optional[datetime] = None
    published_at:        Optional[datetime] = None
    expires_at:          Optional[datetime] = None
    source_org:          str = Field(..., min_length=2, max_length=64)
    source_url:          Optional[str] = Field(None, max_length=512)
    source_id:           Optional[str] = Field(None, max_length=64)
    ingestion_run_id:    Optional[str] = Field(None, max_length=64)
    district:            Optional[str] = Field(None, max_length=64)
    province:            Optional[str] = Field(None, max_length=64)
    latitude:            Optional[float] = None
    longitude:           Optional[float] = None
    language:            str = Field("en")
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


class AlertHistoryEntry(BaseModel):
    changed_at: datetime
    changed_by: Optional[str]
    field_name: str
    old_value:  Optional[str]
    new_value:  Optional[str]
    action:     str
    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    alert_id:            str
    title:               str
    body:                str
    hazard_type:         str
    severity:            str
    issued_at:           datetime
    published_at:        Optional[datetime]
    fetch_timestamp:     Optional[datetime]
    expires_at:          Optional[datetime]
    source_org:          str
    source_url:          Optional[str]
    source_id:           Optional[str]
    ingestion_run_id:    Optional[str]
    verification_status: str
    district:            Optional[str]
    province:            Optional[str]
    latitude:            Optional[float]
    longitude:           Optional[float]
    language:            str
    is_active:           bool
    created_at:          datetime
    # Phase 2.3: added to let Flutter UI label location precision honestly.
    # Values: "coordinate" | "district_name" | "province_only" | "national"
    # Defaults to None when the response is not produced by a location query.
    location_match_type: Optional[str] = None
    model_config = {"from_attributes": True}


class AlertDetailResponse(AlertResponse):
    """Full alert with audit history."""
    history: list[AlertHistoryEntry] = []


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
