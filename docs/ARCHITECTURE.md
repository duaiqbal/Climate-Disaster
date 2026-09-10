# Disaster DSS — Architecture

## System Overview

Disaster DSS is an **offline-first, multilingual disaster decision-support system** for Chitral, KP.  
It is explicitly **not** a real-time prediction model and **not** an official emergency alert system.  
It is a decision-support layer that makes existing verified official guidance accessible, location-aware, and understandable with zero internet or electricity.

---

## Core Design Principle

> **Generation is optional. Verified retrieval and deterministic rules are mandatory.**

The core system operates with:
- Zero internet
- Zero cloud LLM
- Zero local LLM
- Zero paid APIs

AI generation is an optional post-processing layer that can only rephrase already-retrieved, verified content. It is never allowed to generate new facts, alerts, or predictions.

---

## Component Map

```
disaster_dss/
├── app/                        Flutter mobile application
│   ├── lib/core/
│   │   ├── local_db/           DatabaseHelper — SQLite access layer
│   │   ├── retrieval/          KeywordRetriever + RomanUrduNormalizer
│   │   ├── rules_engine/       HazardRules — deterministic classifier
│   │   ├── localization/       AppLocalizations (en / ur / ru)
│   │   ├── providers/          LanguageProvider, AppStateProvider
│   │   └── theme/              AppTheme (light + dark)
│   ├── lib/features/
│   │   ├── onboarding/         3-page first-run flow
│   │   ├── auth/               Login, Signup (local credential store)
│   │   ├── dashboard/          Bottom-nav shell + home tab
│   │   ├── chat/               Offline Q&A — retrieval + source display
│   │   ├── map/                GPS hazard lookup + indicator display
│   │   ├── alerts/             Local alert cache + optional sync
│   │   ├── safety/             4-tab safety checklist (persistent)
│   │   ├── profile/            Language selector, package meta, logout
│   │   └── simulator/          Demo scenario runner (3 scenarios)
│   └── assets/offline_package/ knowledge.sqlite + hazard_grid.sqlite
│
├── backend/                    FastAPI — optional online sync
│   ├── main.py                 App factory, lifespan, CORS
│   ├── database.py             Async SQLAlchemy + aiosqlite
│   ├── models/db_models.py     ORM models + Pydantic schemas
│   └── routers/
│       ├── alerts.py           CRUD endpoints for official alerts
│       ├── auth.py             Register / Login / token
│       ├── knowledge.py        Read-only chunk browser + search
│       └── sync.py             Package version sync
│
├── pipeline/                   Laptop-side data processing
│   ├── rag/extract.py          PDF → JSON (PyMuPDF)
│   ├── rag/chunk.py            JSON → overlapping text chunks
│   ├── rag/embed.py            Chunks → embeddings (multilingual MiniLM)
│   ├── package_builder/
│   │   └── build_sqlite.py     Chunks + alerts → knowledge.sqlite
│   ├── gis/
│   │   └── compute_hazard_grid.py  DEM + OSM → hazard_grid.sqlite
│   └── run_pipeline.py         End-to-end runner
│
├── fetchers/                   Data ingestion helpers
│   ├── pdma_kp_fetcher.py      Manual advisory ingestor (validated)
│   └── ndma_scraper.py         Web scraper (review gate before ingest)
│
├── evaluation/
│   ├── retrieval_eval.py       P@K, R@K, MRR, F1 per language + hazard type
│   └── eval_summary.json       Latest evaluation output
│
├── data/
│   ├── raw/                    Official PDFs (gitignored)
│   ├── extracted/              Per-doc JSON (gitignored)
│   ├── chunks/                 Chunk JSON files (gitignored)
│   ├── embeddings/             FAISS index + numpy arrays (gitignored)
│   ├── raw_advisories.json     Ingested advisories (versioned)
│   └── ground_truth_eval.json  Evaluation ground truth (versioned)
│
├── offline_package/
│   ├── knowledge.sqlite        Built knowledge DB (gitignored)
│   ├── hazard_grid.sqlite      Built GIS grid (gitignored)
│   └── manifest.json           Version + checksum record
│
└── docs/
    ├── ARCHITECTURE.md         This file
    └── MANUAL_CRITERIA_GUIDE.md  Source evaluation criteria
```

---

## Data Flow

### Offline Query (primary path — zero internet required)

```
User types query
      │
      ▼
KeywordRetriever.retrieve()
      │  ├─ Roman Urdu? → RomanUrduNormalizer.expandQuery()
      │  └─ LIKE search over chunks table (SQLite)
      │
      ▼
List<RetrievalResult>
      │  Each result carries: chunk_text, source_org, pub_date, evidence_level
      │
      ▼
ChatScreen renders results with source badges
      │  No generation. No inference. Verified text only.
      ▼
User sees answer + source attribution
```

### Location Hazard Check (offline — GPS only)

```
User opens Hazard Map
      │
      ▼
Geolocator.getCurrentPosition()
      │
      ▼
DatabaseHelper.getHazardCell(lat, lon)
      │  SELECT from hazard_grid.sqlite WHERE lat BETWEEN … AND lon BETWEEN …
      │
      ▼
HazardRules.classify(slopeDeg, riverDistKm, elevationM)
      │  Deterministic threshold rules — same logic in Dart and Python
      │
      ▼
HazardAssessment (HIGH / MEDIUM / LOW)
      │  + contributing factors + ALWAYS shown with indicator disclaimer
      ▼
HazardMapScreen displays result
```

### Optional Online Sync

```
AppStateProvider detects connectivity
      │
      ▼
AlertsScreen.syncAlerts() → HTTP GET /alerts (FastAPI backend)
      │
      ▼
DatabaseHelper.upsertAlert() → writes to local SQLite
      │
      ▼
App continues using local SQLite — connection can be lost at any point
```

---

## Offline Package Build Pipeline

```
data/raw/*.pdf
      │
      ▼  pipeline/rag/extract.py (PyMuPDF)
data/extracted/*.json
      │
      ▼  pipeline/rag/chunk.py (paragraph split + overlap)
data/chunks/*.json
      │
      ├─▶ pipeline/rag/embed.py (multilingual MiniLM → FAISS)
      │   data/embeddings/  [backend-only, not shipped to app]
      │
      ▼  pipeline/package_builder/build_sqlite.py
offline_package/knowledge.sqlite
      │
      ▼  Copy to app/assets/offline_package/

data/raw/chitral_dem.tif  +  data/raw/chitral_rivers.gpkg
      │                       [Copernicus DEM + OSM — or synthetic fallback]
      ▼  pipeline/gis/compute_hazard_grid.py
offline_package/hazard_grid.sqlite
      │
      ▼  Copy to app/assets/offline_package/
```

---

## SQLite Schema (knowledge.sqlite)

```sql
CREATE TABLE chunks (
    chunk_id       TEXT PRIMARY KEY,
    source_org     TEXT NOT NULL,      -- NDMA / PDMA KP / PMD
    doc_title      TEXT NOT NULL,
    pub_date       TEXT,
    language       TEXT NOT NULL,      -- en / ur / ru
    page_num       INTEGER,
    chunk_index    INTEGER,
    chunk_text     TEXT NOT NULL,
    keywords       TEXT,               -- comma-separated disaster keywords
    evidence_level TEXT,               -- official_national / official_provincial / …
    char_count     INTEGER
);

CREATE TABLE alerts (
    alert_id    TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    hazard_type TEXT,                  -- flood / flash_flood / landslide
    severity    TEXT,                  -- LOW / MEDIUM / HIGH / EXTREME
    issued_at   TEXT,
    source_org  TEXT,
    district    TEXT
);

CREATE TABLE package_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
```

## SQLite Schema (hazard_grid.sqlite)

```sql
CREATE TABLE hazard_grid (
    cell_id              TEXT PRIMARY KEY,
    lat                  REAL NOT NULL,
    lon                  REAL NOT NULL,
    elevation_m          REAL,
    slope_deg            REAL,
    river_dist_km        REAL,
    hazard_level         TEXT NOT NULL,   -- HIGH / MEDIUM / LOW
    contributing_factors TEXT             -- JSON array of factor strings
);
```

---

## Hazard Classification Rules

These rules are identical in `pipeline/gis/compute_hazard_grid.py` (Python) and `app/lib/core/rules_engine/hazard_rules.dart` (Dart). Any change must be applied to both.

```
Flood HIGH   : river_dist_km < 0.5  AND elevation_m < 2000
Flood MEDIUM : river_dist_km < 1.5
Flood LOW    : otherwise

Landslide HIGH   : slope_deg > 30°
Landslide MEDIUM : slope_deg > 15°
Landslide LOW    : otherwise

Overall = worst-case combination (HIGH beats MEDIUM beats LOW)
```

All outputs are labeled **"indicator, not prediction"** — explicitly in the UI and in the manifest.

---

## Retrieval Strategy

| Language | Strategy |
|----------|----------|
| English | Tokenise → LIKE search on `chunk_text` + `keywords` |
| Urdu | Same — Urdu tokens match directly against Urdu chunks |
| Roman Urdu | `RomanUrduNormalizer.expandQuery()` expands each token to all known spelling variants, then LIKE search; falls back to English if no results |

No vector/semantic search is used on-device. FAISS embeddings exist only on the laptop/backend for optional semantic ranking.

---

## Technology Rationale

| Decision | Reason |
|----------|--------|
| SQLite not FTS5 | FTS5 availability varies across Android SQLite builds; LIKE is universally available |
| Keyword not vector retrieval on-device | Reliable across all Android versions; no native library dependencies; deterministic |
| Multilingual MiniLM for embeddings | Free, open-source, supports en/ur/Roman Urdu; ~118 MB; CPU-viable |
| Flutter not React Native | Single codebase; first-class SQLite support; good offline story |
| FastAPI not Django | Lightweight; matches small endpoint surface; async-native |
| Synthetic terrain fallback | Makes the system runnable without Copernicus DEM download; clearly labeled |

---

## Security Notes

- All write endpoints on the backend require `X-Admin-Key` header
- Passwords hashed with PBKDF2-HMAC-SHA256, 200,000 iterations
- Tokens signed with HMAC-SHA256; TTL = 24h
- No PII is stored on-device beyond local SharedPreferences (name, email)
- The app does not transmit location data to any server
- `ADMIN_API_KEY` and `SECRET_KEY` must be set via environment variables in production (never hardcoded)
