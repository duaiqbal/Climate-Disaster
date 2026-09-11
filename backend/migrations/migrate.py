"""
backend/migrations/migrate.py
==============================
Non-destructive migration script.

Applies schema changes to an EXISTING database without dropping any table.
Safe to run multiple times — each step is idempotent.

Strategy:
  1. For each new table: CREATE TABLE IF NOT EXISTS
  2. For each new column on existing tables: ADD COLUMN IF NOT EXISTS
     (SQLite: wrapped in try/except since it doesn't support IF NOT EXISTS on columns)
     (PostgreSQL: ALTER TABLE ... ADD COLUMN IF NOT EXISTS is supported natively)
  3. For each new index: CREATE INDEX IF NOT EXISTS

Run:
  python backend/migrations/migrate.py
  python backend/migrations/migrate.py --db sqlite:////tmp/disaster_dss_backend.sqlite
  python backend/migrations/migrate.py --db postgresql+psycopg2://user:pass@host/db

The script uses synchronous SQLAlchemy (via create_engine, not async) so it
can be run as a standalone CLI without an event loop.
"""

import argparse
import sys
from pathlib import Path

# Allow running from project root or from this file's directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, inspect, text

# ── Helpers ────────────────────────────────────────────────────────────────────

def _table_exists(conn, table_name: str) -> bool:
    insp = inspect(conn)
    return table_name in insp.get_table_names()


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    insp = inspect(conn)
    if not _table_exists(conn, table_name):
        return False
    return any(c["name"] == column_name for c in insp.get_columns(table_name))


def _index_exists(conn, index_name: str) -> bool:
    insp = inspect(conn)
    for table in insp.get_table_names():
        for idx in insp.get_indexes(table):
            if idx["name"] == index_name:
                return True
    return False


def _exec(conn, sql: str, label: str) -> None:
    try:
        conn.execute(text(sql))
        print(f"  OK  {label}")
    except Exception as e:
        print(f"  SKIP {label}: {e}")


# ── Migration steps ────────────────────────────────────────────────────────────

def run_migration(db_url: str) -> None:
    print(f"\nMigration target: {db_url}")
    is_sqlite = "sqlite" in db_url

    engine = create_engine(db_url)

    with engine.begin() as conn:

        # ── 1. sources table ──────────────────────────────────────────────────
        if not _table_exists(conn, "sources"):
            _exec(conn, """
                CREATE TABLE sources (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id       VARCHAR(64) NOT NULL UNIQUE,
                    org             VARCHAR(64) NOT NULL,
                    doc_title       VARCHAR(255),
                    source_url      VARCHAR(512) NOT NULL,
                    fetched_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    checksum_sha256 VARCHAR(64),
                    content_type    VARCHAR(64),
                    language        VARCHAR(8) NOT NULL DEFAULT 'en',
                    is_active       BOOLEAN NOT NULL DEFAULT 1,
                    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """ if is_sqlite else """
                CREATE TABLE IF NOT EXISTS sources (
                    id              SERIAL PRIMARY KEY,
                    source_id       VARCHAR(64) NOT NULL UNIQUE,
                    org             VARCHAR(64) NOT NULL,
                    doc_title       VARCHAR(255),
                    source_url      VARCHAR(512) NOT NULL,
                    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    checksum_sha256 VARCHAR(64),
                    content_type    VARCHAR(64),
                    language        VARCHAR(8) NOT NULL DEFAULT 'en',
                    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """, "CREATE TABLE sources")
        else:
            print("  SKIP CREATE TABLE sources (already exists)")

        # ── 2. ingestion_runs table ───────────────────────────────────────────
        if not _table_exists(conn, "ingestion_runs"):
            _exec(conn, """
                CREATE TABLE ingestion_runs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id          VARCHAR(64) NOT NULL UNIQUE,
                    started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    finished_at     DATETIME,
                    trigger         VARCHAR(32) NOT NULL DEFAULT 'scheduled',
                    status          VARCHAR(16) NOT NULL DEFAULT 'running',
                    sources_checked INTEGER NOT NULL DEFAULT 0,
                    new_found       INTEGER NOT NULL DEFAULT 0,
                    alerts_created  INTEGER NOT NULL DEFAULT 0,
                    alerts_skipped  INTEGER NOT NULL DEFAULT 0,
                    error_message   TEXT,
                    runner_version  VARCHAR(32)
                )
            """ if is_sqlite else """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    id              SERIAL PRIMARY KEY,
                    run_id          VARCHAR(64) NOT NULL UNIQUE,
                    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    finished_at     TIMESTAMPTZ,
                    trigger         VARCHAR(32) NOT NULL DEFAULT 'scheduled',
                    status          VARCHAR(16) NOT NULL DEFAULT 'running',
                    sources_checked INTEGER NOT NULL DEFAULT 0,
                    new_found       INTEGER NOT NULL DEFAULT 0,
                    alerts_created  INTEGER NOT NULL DEFAULT 0,
                    alerts_skipped  INTEGER NOT NULL DEFAULT 0,
                    error_message   TEXT,
                    runner_version  VARCHAR(32)
                )
            """, "CREATE TABLE ingestion_runs")
        else:
            print("  SKIP CREATE TABLE ingestion_runs (already exists)")

        # ── 3. alert_history table ────────────────────────────────────────────
        if not _table_exists(conn, "alert_history"):
            _exec(conn, """
                CREATE TABLE alert_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_db_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
                    changed_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    changed_by  VARCHAR(64),
                    field_name  VARCHAR(64) NOT NULL,
                    old_value   TEXT,
                    new_value   TEXT,
                    action      VARCHAR(32) NOT NULL
                )
            """ if is_sqlite else """
                CREATE TABLE IF NOT EXISTS alert_history (
                    id          SERIAL PRIMARY KEY,
                    alert_db_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
                    changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    changed_by  VARCHAR(64),
                    field_name  VARCHAR(64) NOT NULL,
                    old_value   TEXT,
                    new_value   TEXT,
                    action      VARCHAR(32) NOT NULL
                )
            """, "CREATE TABLE alert_history")
        else:
            print("  SKIP CREATE TABLE alert_history (already exists)")

        # ── 4. New columns on alerts ──────────────────────────────────────────
        new_alert_cols = [
            ("source_id",        "VARCHAR(64)"),
            ("ingestion_run_id", "VARCHAR(64)"),
            ("published_at",     "DATETIME"),
            ("expires_at",       "DATETIME"),
            ("latitude",         "FLOAT"),
            ("longitude",        "FLOAT"),
            ("province",         "VARCHAR(64)"),
        ]
        for col_name, col_type in new_alert_cols:
            if not _column_exists(conn, "alerts", col_name):
                _exec(conn,
                      f"ALTER TABLE alerts ADD COLUMN {col_name} {col_type}",
                      f"ALTER TABLE alerts ADD COLUMN {col_name}")
            else:
                print(f"  SKIP ALTER TABLE alerts ADD COLUMN {col_name} (already exists)")

        # ── 5. New columns on users ───────────────────────────────────────────
        if not _column_exists(conn, "users", "updated_at"):
            _exec(conn,
                  "ALTER TABLE users ADD COLUMN updated_at DATETIME",
                  "ALTER TABLE users ADD COLUMN updated_at")

        # ── 6. Indexes (all idempotent: CREATE INDEX IF NOT EXISTS) ───────────
        indexes = [
            # sources
            ("ix_sources_org",         "sources",        "org"),
            ("ix_sources_source_url",  "sources",        "source_url"),
            ("ix_sources_fetched_at",  "sources",        "fetched_at"),
            ("ix_sources_checksum",    "sources",        "checksum_sha256"),
            # ingestion_runs
            ("ix_ingestion_runs_started_at", "ingestion_runs", "started_at"),
            ("ix_ingestion_runs_status",     "ingestion_runs", "status"),
            # alert_history
            ("ix_alert_history_alert_db_id", "alert_history",  "alert_db_id"),
            ("ix_alert_history_changed_at",  "alert_history",  "changed_at"),
            ("ix_alert_history_action",      "alert_history",  "action"),
            # alerts — new columns
            ("ix_alerts_published_at",       "alerts",         "published_at"),
            ("ix_alerts_source_id",          "alerts",         "source_id"),
            ("ix_alerts_ingestion_run_id",   "alerts",         "ingestion_run_id"),
            ("ix_alerts_district_hazard",    "alerts",         "district, hazard_type"),
            ("ix_alerts_latitude",           "alerts",         "latitude"),
            ("ix_alerts_longitude",          "alerts",         "longitude"),
        ]
        for idx_name, tbl, col in indexes:
            if not _index_exists(conn, idx_name):
                _exec(conn,
                      f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl}({col})",
                      f"CREATE INDEX {idx_name}")
            else:
                print(f"  SKIP CREATE INDEX {idx_name} (already exists)")

    print(f"\nMigration complete.\n")


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    parser = argparse.ArgumentParser(description="Disaster DSS — non-destructive schema migration")
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL", "").replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2") or None,
        help="SQLAlchemy database URL (sync driver). Defaults to DATABASE_URL env var.",
    )
    args = parser.parse_args()

    if not args.db:
        # Default: same TEMP path as config.py uses
        import tempfile
        db_path = Path(tempfile.gettempdir()) / "disaster_dss_backend.sqlite"
        args.db = f"sqlite:///{db_path}"
        print(f"No --db specified. Using: {args.db}")

    run_migration(args.db)
