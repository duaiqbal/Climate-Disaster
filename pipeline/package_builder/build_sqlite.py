"""
pipeline/package_builder/build_sqlite.py
=========================================
Step 4: Build the offline SQLite knowledge database from all chunks.

Input:  data/chunks/*.json
Output: offline_package/knowledge.sqlite

Schema:
  CREATE TABLE chunks (
      chunk_id       TEXT PRIMARY KEY,
      source_org     TEXT NOT NULL,
      doc_title      TEXT NOT NULL,
      pub_date       TEXT,
      language       TEXT NOT NULL,
      page_num       INTEGER,
      chunk_index    INTEGER,
      chunk_text     TEXT NOT NULL,
      keywords       TEXT,
      evidence_level TEXT,
      char_count     INTEGER
  );

  CREATE TABLE alerts (
      alert_id    TEXT PRIMARY KEY,
      title       TEXT NOT NULL,
      body        TEXT NOT NULL,
      hazard_type TEXT,
      severity    TEXT,
      issued_at   TEXT,
      source_org  TEXT,
      district    TEXT
  );

  CREATE TABLE package_meta (
      key   TEXT PRIMARY KEY,
      value TEXT
  );

The build script:
- Inserts all chunks
- Inserts seed alerts for demo
- Records version, build timestamp, chunk count, source doc count
- Creates indexes on language and keywords for fast LIKE queries
"""

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
CHUNKS_DIR = ROOT / "data" / "chunks"
OUT_DIR = ROOT / "offline_package"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = OUT_DIR / "knowledge.sqlite"

# Package version — bump when content changes
PACKAGE_VERSION = "1.0.0"

# ── Seed alerts (displayed when no online data has been synced yet) ───────────
SEED_ALERTS = [
    {
        "alert_id": "seed_001",
        "title": "Monsoon Season Advisory – Chitral",
        "body": (
            "NDMA advises all communities in Chitral district to remain on high alert "
            "during the monsoon season (July–September). Avoid river banks, steep "
            "slopes, and narrow valleys during heavy rainfall. Keep a 72-hour "
            "emergency kit ready. PDMA KP Helpline: 1700."
        ),
        "hazard_type": "flood",
        "severity": "MEDIUM",
        "issued_at": "2024-06-01T00:00:00",
        "source_org": "NDMA",
        "district": "Chitral",
    },
    {
        "alert_id": "seed_002",
        "title": "Landslide Risk Advisory – Upper Chitral",
        "body": (
            "PDMA KP warns of elevated landslide risk in Upper Chitral following "
            "prolonged rainfall. Communities on or below steep slopes should "
            "identify evacuation routes. Report visible cracks or ground movement "
            "to local administration immediately."
        ),
        "hazard_type": "landslide",
        "severity": "HIGH",
        "issued_at": "2024-07-10T00:00:00",
        "source_org": "PDMA KP",
        "district": "Chitral",
    },
    {
        "alert_id": "seed_003",
        "title": "Flash Flood Early Warning – Chitral River",
        "body": (
            "PMD has issued a flash flood watch for the Chitral River catchment. "
            "Heavy rainfall forecast in the upper catchment over the next 48 hours "
            "may cause rapid rise in river levels. Avoid river crossings. "
            "Monitor official channels for updates."
        ),
        "hazard_type": "flash_flood",
        "severity": "HIGH",
        "issued_at": "2024-08-05T06:00:00",
        "source_org": "PMD",
        "district": "Chitral",
    },
    {
        "alert_id": "seed_004",
        "title": "سیلاب الرٹ – چترال",
        "body": (
            "این ڈی ایم اے چترال: موسم برسات کے دوران دریاؤں کے قریب نہ جائیں۔ "
            "اونچی جگہ پر جانے کا منصوبہ بنائیں۔ ہنگامی کٹ تیار رکھیں۔ "
            "پی ڈی ایم اے ہیلپ لائن: 1700"
        ),
        "hazard_type": "flood",
        "severity": "MEDIUM",
        "issued_at": "2024-06-15T00:00:00",
        "source_org": "NDMA",
        "district": "Chitral",
    },
]


def load_chunks() -> list[dict]:
    all_chunks: list[dict] = []
    for fp in sorted(CHUNKS_DIR.glob("*.json")):
        with open(fp, encoding="utf-8") as f:
            chunks = json.load(f)
        all_chunks.extend(chunks)
    return all_chunks


def compute_checksum(db_path: Path) -> str:
    h = hashlib.sha256()
    with open(db_path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS chunks;
        DROP TABLE IF EXISTS alerts;
        DROP TABLE IF EXISTS package_meta;

        CREATE TABLE chunks (
            chunk_id       TEXT PRIMARY KEY,
            source_org     TEXT NOT NULL,
            doc_title      TEXT NOT NULL,
            pub_date       TEXT,
            language       TEXT NOT NULL,
            page_num       INTEGER,
            chunk_index    INTEGER,
            chunk_text     TEXT NOT NULL,
            keywords       TEXT,
            evidence_level TEXT,
            char_count     INTEGER
        );

        CREATE TABLE alerts (
            alert_id    TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            body        TEXT NOT NULL,
            hazard_type TEXT,
            severity    TEXT,
            issued_at   TEXT,
            source_org  TEXT,
            district    TEXT
        );

        CREATE TABLE package_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)


def create_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_chunks_language
            ON chunks(language);
        CREATE INDEX IF NOT EXISTS idx_chunks_source_org
            ON chunks(source_org);
        CREATE INDEX IF NOT EXISTS idx_alerts_issued_at
            ON alerts(issued_at DESC);
        CREATE INDEX IF NOT EXISTS idx_alerts_district
            ON alerts(district);
    """)


def insert_chunks(conn: sqlite3.Connection, chunks: list[dict]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO chunks
          (chunk_id, source_org, doc_title, pub_date, language,
           page_num, chunk_index, chunk_text, keywords, evidence_level, char_count)
        VALUES
          (:chunk_id, :source_org, :doc_title, :pub_date, :language,
           :page_num, :chunk_index, :chunk_text, :keywords, :evidence_level, :char_count)
        """,
        chunks,
    )


def insert_alerts(conn: sqlite3.Connection, alerts: list[dict]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO alerts
          (alert_id, title, body, hazard_type, severity, issued_at, source_org, district)
        VALUES
          (:alert_id, :title, :body, :hazard_type, :severity, :issued_at, :source_org, :district)
        """,
        alerts,
    )


def insert_meta(conn: sqlite3.Connection, meta: dict) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO package_meta (key, value) VALUES (?, ?)",
        [(k, str(v)) for k, v in meta.items()],
    )


def main():
    chunks = load_chunks()
    if not chunks:
        print(f"No chunks found in {CHUNKS_DIR}")
        print("Run extract.py and chunk.py first.")
        sys.exit(1)

    print(f"Building knowledge.sqlite from {len(chunks)} chunks…")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    create_schema(conn)
    insert_chunks(conn, chunks)
    insert_alerts(conn, SEED_ALERTS)
    create_indexes(conn)

    # Collect stats
    source_docs = {c["source_file"] for c in chunks}
    lang_counts: dict[str, int] = {}
    for c in chunks:
        lang_counts[c["language"]] = lang_counts.get(c["language"], 0) + 1

    built_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "version": PACKAGE_VERSION,
        "built_at": built_at,
        "chunk_count": len(chunks),
        "alert_count": len(SEED_ALERTS),
        "source_docs": len(source_docs),
        "lang_en": lang_counts.get("en", 0),
        "lang_ur": lang_counts.get("ur", 0),
        "lang_ru": lang_counts.get("ru", 0),
        "grid_cell_count": "see hazard_grid.sqlite",
    }
    insert_meta(conn, meta)

    conn.commit()
    conn.close()

    # Checksum
    checksum = compute_checksum(DB_PATH)
    size_kb = DB_PATH.stat().st_size // 1024

    # Save manifest sidecar
    manifest_path = OUT_DIR / "manifest.json"
    manifest = {
        **meta,
        "knowledge_sqlite_checksum_sha256": checksum,
        "knowledge_sqlite_size_kb": size_kb,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n── Build complete ──────────────────────────────────")
    print(f"  Database  : {DB_PATH}  ({size_kb} KB)")
    print(f"  Chunks    : {len(chunks)}")
    print(f"  Alerts    : {len(SEED_ALERTS)}")
    print(f"  Sources   : {len(source_docs)} documents")
    print(f"  Languages : en={lang_counts.get('en',0)}, "
          f"ur={lang_counts.get('ur',0)}, ru={lang_counts.get('ru',0)}")
    print(f"  SHA-256   : {checksum[:16]}…")
    print(f"  Manifest  : {manifest_path}")
    print(f"\nNext: Copy to app/assets/offline_package/knowledge.sqlite")


if __name__ == "__main__":
    main()
