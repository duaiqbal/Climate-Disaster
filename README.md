# Disaster DSS – Chitral, KP

**Offline-first, multilingual disaster decision-support system for flood and landslide-prone communities in Chitral, Khyber Pakhtunkhwa, Pakistan.**

> **Not an official emergency alert system. Not a validated prediction model.**
> A decision-support layer that makes existing verified official guidance accessible,
> location-aware, and understandable — with zero internet and zero electricity.

---

## The Problem

During floods, flash floods, and landslides in mountainous Chitral:

- Electricity and internet fail **exactly when needed most**
- Official NDMA/PDMA advisories become **inaccessible**
- Advisories are written in formal English, **difficult for local communities**
- No offline, location-specific way exists to understand **personal hazard exposure**

---

## Core Design Principle

> **Generation is optional. Verified retrieval and deterministic rules are mandatory.**

The core app works with **zero internet, zero cloud LLM, and zero local LLM.**
AI generation is only ever an optional layer that rephrases already-retrieved verified
content — it is never allowed to invent facts, alerts, or predictions.

---

## Key Features

| Feature | How it works | Status |
|---------|-------------|--------|
| **Offline Q&A** | SQLite keyword search over verified NDMA/PDMA/PMD chunks — airplane mode | ✅ Implemented |
| **AI-Powered Chat** | Optional Ollama (Llama3) local LLM for natural language generation | ✅ Implemented |
| **Real-Time Alerts** | Scheduled NDMA scraper (every 6 hours) with APScheduler | ✅ Implemented |
| **Multilingual** | English, Urdu, Roman Urdu — spelling-variant expansion for Roman Urdu | ✅ Implemented |
| **Location hazard indicator** | GPS lookup against precomputed GIS grid (slope + river proximity) | ✅ Implemented |
| **Source transparency** | Every answer shows organisation, publication date, evidence level | ✅ Implemented |
| **Safety checklists** | Go-bag, flood, landslide, evacuation — persistent across sessions | ✅ Implemented |
| **Official alerts** | Cached locally, syncs from backend when online | ✅ Implemented |
| **Online sync** | FastAPI backend for fresher alerts and package updates (optional) | ✅ Implemented |
| **Data provenance** | Every offline package has version, checksum, build timestamp | ✅ Implemented |

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Mobile / Web app | Flutter / Dart |
| Offline database | SQLite (LIKE queries, no FTS5 dependency) |
| Embeddings (laptop only) | Sentence-Transformers multilingual MiniLM |
| Vector search (backend only) | FAISS |
| Backend | FastAPI + aiosqlite |
| GIS processing (laptop only) | Rasterio, GeoPandas, Shapely |
| Elevation data | Copernicus DEM / SRTM (synthetic fallback) |
| River data | OpenStreetMap (synthetic fallback) |

**No mandatory paid API, cloud credit, or GPU anywhere in the core system.**

---

## Hazard Scope

**In scope:** Flood · Flash Flood · Landslide

**Out of scope (future work):** GLOF, household ML risk prediction, multi-province
deployment, real-time government API integration.

---

## Quick Start (Complete Setup)

**Automated setup script:**

```powershell
cd disaster_dss
.\setup_complete_system.ps1
```

This script will:
1. ✓ Check Ollama installation (AI model runtime)
2. ✓ Pull Llama3 model (~4.7GB) if needed
3. ✓ Create backend `.env` configuration
4. ✓ Install Python dependencies
5. ✓ Run database migrations
6. ✓ Test the system

**Manual setup:** See `SETUP_AI_REALTIME.md`

---

## Running the System

**Terminal 1 — Backend (AI + Real-Time Alerts):**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload --port 8002
```

**Terminal 2 — Flutter Web:**
```powershell
cd app
flutter run -d chrome --web-port 8080
```

**Open:** http://localhost:8080

---

## What You Get

### 1. AI-Powered Chat
- Ask: "What should I do during heavy rain in Chitral?"
- System retrieves verified NDMA/PDMA chunks
- Llama3 (local) rephrases into natural language
- Shows sources + evidence level

### 2. Real-Time Alert Monitoring
- Backend scrapes NDMA website every 6 hours
- Alert lifecycle: DISCOVERED → VERIFIED → PUBLISHED
- Manual trigger: `POST /monitor/run`
- Status check: `GET /monitor/status`

### 3. Offline Mode
- **Everything works without internet**
- 315 document chunks in SQLite
- 10,000 hazard grid cells (slope + river data)
- Full chat, map, checklist, alerts (cached)

---

## Project Structure

```
disaster_dss/
├── app/                     Flutter mobile + web application
│   ├── lib/core/            config, local_db, retrieval, rules_engine, localization, providers, theme
│   ├── lib/features/        auth, onboarding, dashboard, chat, map, alerts, safety, profile, simulator
│   └── assets/offline_package/   knowledge.sqlite + hazard_grid.sqlite
├── backend/                 FastAPI (optional online mode)
│   ├── main.py
│   ├── database.py
│   ├── models/db_models.py
│   └── routers/             alerts, auth, knowledge, sync
├── pipeline/
│   ├── rag/                 extract.py → chunk.py → embed.py
│   ├── package_builder/     build_sqlite.py
│   ├── gis/                 compute_hazard_grid.py
│   └── run_pipeline.py
├── fetchers/                pdma_kp_fetcher.py, ndma_scraper.py
├── data/                    raw PDFs + ground truth (large files gitignored)
├── evaluation/              retrieval_eval.py, ground_truth_eval.json
├── offline_package/         Built SQLite outputs (gitignored), manifest.json
├── docs/                    ARCHITECTURE.md, MANUAL_CRITERIA_GUIDE.md
├── run_demo.ps1             ← One-command local demo launcher
└── requirements.txt
```

---

## Quick Start

### Prerequisites

- Python 3.10+ (3.11/3.12 recommended)
- Flutter SDK 3.x + Android SDK (for mobile) or Chrome (for web)

### 1 — Python environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2 — Build offline databases

```powershell
python pipeline/run_pipeline.py --skip-embed
```

If no real NDMA/PDMA PDFs are in `data/raw/`, the pipeline auto-generates a
demo PDF with realistic Chitral advisory content so the full app runs immediately.

### 3 — One-command demo launch

```powershell
.\run_demo.ps1
```

This starts:
- FastAPI backend → **http://127.0.0.1:8000**
- Flutter Web → **http://localhost:8080**

Open **http://localhost:8080** in your browser.

### 4 — Run on Android emulator / device

```powershell
cd app
flutter pub get
flutter run
```

For a physical device, pass your machine's LAN IP:

```powershell
flutter run --dart-define=BACKEND_URL=http://192.168.1.x:8000
```

### 5 — Backend only

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

API docs: **http://127.0.0.1:8000/docs**

---

## Demo Scenarios

### Scenario 1 — Airplane Mode Query
Device in airplane mode. Ask: *"What should I do during a flood?"*
→ Verified NDMA/PDMA guidance with source, publication date, and evidence level.
Zero network requests made.

### Scenario 2 — Location Hazard Check
GPS locates you in Chitral.
→ App queries `hazard_grid.sqlite` offline, returns hazard level (HIGH/MEDIUM/LOW)
with contributing terrain factors and explicit indicator disclaimer.

### Scenario 3 — Roman Urdu Query
Ask: *"Flood mein kya karein?"*
→ `RomanUrduNormalizer` expands spelling variants, retrieves relevant official
guidance, falls back to English if needed.

---

## Offline Package — Actual Current State

| File | Contents | Size |
|------|----------|------|
| `knowledge.sqlite` | Chunks from official source PDFs | ~76 KB (seed build) |
| `hazard_grid.sqlite` | 10,000 precomputed hazard cells at 0.01° | ~2 MB |

**knowledge.sqlite current state:** The bundled database contains chunks extracted
from available official documents plus seed alerts. Run the full pipeline with real
NDMA/PDMA/PMD PDFs in `data/raw/` to expand the knowledge base.

**Hazard grid:** 10,000 cells covering lat 35.50–36.50, lon 71.50–72.50 (Chitral).
Generated with a Chitral-calibrated synthetic terrain model (slope + river proximity).
Distribution: HIGH ~8,499 · MEDIUM ~1,064 · LOW ~437 cells.

> **Important:** The hazard grid is a coarse indicator based on modelled terrain —
> NOT a validated scientific prediction. It does not replace official NDMA/PDMA warnings.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| POST | `/auth/register` | User registration |
| POST | `/auth/login` | Authentication + token |
| GET | `/alerts` | List alerts (filterable) |
| POST | `/alerts` | Create alert (admin key) |
| GET | `/knowledge/search?q=…` | Keyword search over chunks |
| GET | `/knowledge/chunks` | Paginated chunk list |
| GET | `/knowledge/meta` | Package metadata |
| GET | `/sync/status` | Latest package version |

Full interactive docs at `/docs` when backend is running.

---

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `BACKEND_URL` | auto (web/emulator) | Flutter backend URL (`--dart-define`) |
| `ADMIN_API_KEY` | dev key | Backend write endpoint protection |
| `SECRET_KEY` | dev secret | Token signing — **change in production** |
| `DATABASE_URL` | SQLite | Swap to `postgresql+asyncpg://` for production |
| `KNOWLEDGE_DB` | auto-detected | Path to knowledge.sqlite for backend |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

**Production checklist:**
- Set `SECRET_KEY` to a random 32-byte secret
- Set `ADMIN_API_KEY` to a strong random key
- Set `CORS_ORIGINS` to your actual frontend domain
- Deploy backend behind HTTPS (nginx/caddy)
- Replace SQLite with PostgreSQL for multi-user deployments

---

## Evaluation

```powershell
python evaluation/retrieval_eval.py --k 5
```

**Ground truth:** 27 queries — 14 English, 6 Urdu, 7 Roman Urdu — across flood,
flash flood, landslide, preparedness. Self-constructed by project team (not an
external benchmark — explicitly labeled as such in all outputs).

---

## Honest Limitations

| Limitation | Detail |
|-----------|--------|
| Keyword retrieval only (on-device) | No semantic/vector search in the Flutter app — intentional for offline reliability |
| Hazard grid is synthetic | Slope + river proximity model, not field-validated sensor data |
| No live official API | No public NDMA/PDMA API exists; alert ingestion is manual and verified |
| knowledge.sqlite is a seed build | 76 KB seed — expand by running pipeline with real PDFs |
| Fonts use system fallback | NotoNastaliqUrdu not bundled — Urdu renders in system font |
| Token storage | SharedPreferences (prototype-safe); upgrade to flutter_secure_storage for production |
| No token refresh | 24-hour tokens expire with no automatic renewal |
| Roman Urdu locale code | Uses `Locale('ru')` internally — no conflict in practice |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, branch conventions, pre-push
checklist, source inclusion criteria, and design constraints that must not be violated.

---

## Data Sources

- [NDMA Pakistan](https://ndma.gov.pk)
- [PDMA KP](https://pdma.gov.pk)
- [PMD Pakistan](https://pmd.gov.pk)
- [Copernicus DEM](https://spacedata.copernicus.eu)
- [OpenStreetMap](https://openstreetmap.org)

No proprietary or paid data sources used anywhere in the system.

---

## License

MIT License

---

## Contributors

- **Tooba Iqbal**
- **Kiran Shams**
- **Manahill Khitab**
