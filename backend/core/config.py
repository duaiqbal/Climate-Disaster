"""
backend/core/config.py
=======================
Centralised configuration with environment variable validation.

PRODUCTION BEHAVIOUR:
  If ENV=production and required secrets are still at their default
  development values, the application REFUSES TO START.
  This prevents accidentally running production with dev credentials.

Usage:
  from backend.core.config import settings

  settings.secret_key        # JWT signing secret
  settings.admin_api_key     # Admin endpoint key
  settings.database_url      # SQLAlchemy DB URL
  settings.access_token_ttl  # Access token TTL in seconds
  settings.refresh_token_ttl # Refresh token TTL in seconds
"""

import os
import sys
from pathlib import Path

# ── Sentinel values that must NOT appear in production ────────────────────────
_DEV_SECRET   = "disaster-dss-dev-secret-change-in-production"
_DEV_ADMIN_KEY = "disaster-dss-dev-key-change-in-prod"

_DEFAULT_DB = str(Path(__file__).resolve().parents[2] / "backend" / "disaster_dss_backend.sqlite")


class Settings:
    """All configuration values read from environment variables."""

    def __init__(self) -> None:
        self.env: str = os.getenv("ENV", "development").lower()

        # ── Secrets ───────────────────────────────────────────────────────────
        self.secret_key: str  = os.getenv("SECRET_KEY",   _DEV_SECRET)
        self.admin_api_key: str = os.getenv("ADMIN_API_KEY", _DEV_ADMIN_KEY)

        # ── Database ──────────────────────────────────────────────────────────
        self.database_url: str = os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{_DEFAULT_DB}",
        )

        # ── Token TTLs ────────────────────────────────────────────────────────
        self.access_token_ttl:  int = int(os.getenv("ACCESS_TOKEN_TTL",  "3600"))   # 1 h
        self.refresh_token_ttl: int = int(os.getenv("REFRESH_TOKEN_TTL", "604800")) # 7 d

        # ── CORS ──────────────────────────────────────────────────────────────
        _raw_origins = os.getenv("CORS_ORIGINS", "")
        if _raw_origins:
            self.cors_origins: list[str] = [o.strip() for o in _raw_origins.split(",")]
        else:
            self.cors_origins = [
                "http://localhost:8080",
                "http://localhost:8081",
                "http://localhost:3000",
                "http://127.0.0.1:8080",
                "http://127.0.0.1:3000",
            ]

        # ── Rate limiting ─────────────────────────────────────────────────────
        self.rate_limit_login: str = os.getenv("RATE_LIMIT_LOGIN", "10/minute")

        # ── Features ──────────────────────────────────────────────────────────
        self.sql_echo: bool = bool(os.getenv("SQL_ECHO", ""))

        # ── Production safety check ───────────────────────────────────────────
        if self.env == "production":
            self._validate_production()

    def _validate_production(self) -> None:
        """Refuse to start in production if dev secrets are still in use."""
        errors: list[str] = []

        if self.secret_key == _DEV_SECRET:
            errors.append(
                "SECRET_KEY is still the development default. "
                "Set a strong random SECRET_KEY environment variable."
            )
        if self.admin_api_key == _DEV_ADMIN_KEY:
            errors.append(
                "ADMIN_API_KEY is still the development default. "
                "Set a strong ADMIN_API_KEY environment variable."
            )
        if "sqlite" in self.database_url and "memory" not in self.database_url:
            # SQLite is acceptable for production of small scale but warn
            print(
                "WARNING: Running production with SQLite. "
                "Consider switching DATABASE_URL to PostgreSQL for multi-process deployments.",
                file=sys.stderr,
            )

        if errors:
            print("\n" + "=" * 60, file=sys.stderr)
            print("  STARTUP REFUSED — production security violations:", file=sys.stderr)
            for e in errors:
                print(f"  ✗ {e}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            sys.exit(1)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_development(self) -> bool:
        return self.env == "development"


# Singleton — import this everywhere
settings = Settings()
