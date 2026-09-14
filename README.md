# 🌊 ChitralSafe — Disaster Decision Support System

<p align="center">
  <img src="app/assets/images/app_icon.png" alt="ChitralSafe Logo" width="100"/>
</p>

<p align="center">
  <b>AI-powered offline-first disaster management app for Chitral, KP, Pakistan</b><br/>
  Flutter (Web/Mobile) + FastAPI Backend + RAG AI Chatbot + Real-Time Alerts
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Flutter-3.x-blue?logo=flutter"/>
  <img src="https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi"/>
  <img src="https://img.shields.io/badge/Python-3.12-yellow?logo=python"/>
  <img src="https://img.shields.io/badge/Tests-122%20passing-brightgreen"/>
  <img src="https://img.shields.io/badge/License-MIT-lightgrey"/>
</p>

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Features](#-features)
3. [Architecture](#-architecture)
4. [Quick Start](#-quick-start)
5. [Detailed Setup](#-detailed-setup)
6. [API Documentation](#-api-documentation)
7. [AI / RAG System](#-ai--rag-system)
8. [Testing](#-testing)
9. [Project Structure](#-project-structure)
10. [Team & Contribution](#-team--contribution)

---

## 🎯 Project Overview

ChitralSafe is a Project built for disaster risk management in Chitral, Khyber Pakhtunkhwa, Pakistan. The region faces frequent floods, GLOFs (Glacial Lake Outburst Floods), landslides, and earthquakes.

### Problem
- No offline-capable disaster information system exists for Chitral
- During disasters, internet connectivity is lost
- Local communities lack actionable, multilingual guidance
- Alert information is scattered across NDMA/PDMA websites

### Solution
- **Offline-first Flutter app** — works without internet
- **AI chatbot** powered by RAG (Retrieval-Augmented Generation) over 400+ NDMA/PDMA document chunks
- **Real-time alert scraping** from NDMA, PDMA KP, PMD, and other sources
- **Multilingual** — English, Urdu (اردو), Roman Urdu support
- **Hazard map** — Chitral-specific risk visualization

---

## ✨ Features

### 🤖 AI-Powered RAG Chatbot (Phase 3)
- Searches **400+ verified chunks** from 13 official NDMA/PDMA PDFs
- **Intent-aware retrieval** — detects before/during/after disaster phase
- **Disaster-type classification** — flood, landslide, GLOF, earthquake
- **Alert-aware answers** — injects live alert context into responses
- **Grounding-strict** — never fabricates facts; refuses when evidence insufficient
- **Response cache** — fast repeated queries (TTL: 5 min)
- **FAISS semantic reranking** — optional vector similarity reranking
- Supports **Ollama (local)**, OpenAI, and Groq providers
- **Zero cost** when using Ollama locally

### 🚨 Real-Time Alerts (Phase 2)
- Scrapes **6 official sources**: NDMA, PDMA KP, PMD, PDMA Punjab, ReliefWeb, UN OCHA
- **Alert lifecycle**: `DISCOVERED → VERIFIED → PUBLISHED → ARCHIVED`
- **Provenance tracking**: source org, URL, fetch timestamp, verification status
- **Geographic filtering**: radius-based + province + district filters
- **Soft delete** with audit trail
- **WebSocket** — live alert push to connected Flutter clients
- Background scheduler runs every 6 hours (APScheduler)

### 📱 Flutter App
- **Offline-first** — full functionality without internet
- **Chat screen** — AI chatbot with source attribution
- **Alerts screen** — live alerts with pull-to-refresh
- **Risk dashboard** — hazard map, risk indicators
- **Emergency contacts** — NDMA, PDMA KP, Rescue 1122
- **Multilingual UI** — English / اردو / Roman Urdu toggle
- **Go-bag checklist** — pre-disaster preparation guide
- Runs on **Web (Chrome)**, Android, iOS

### 🔐 Authentication
- JWT access tokens (1 hour TTL)
- Refresh token rotation with revocation
- Admin API key for protected endpoints
- Rate limiting on login endpoint
- Password hashing with bcrypt

### 📊 Knowledge Sync
- Version-controlled knowledge packages
- Offline SQLite knowledge base (ships with app)
- `/sync/status` — check latest knowledge version
- Admin-controlled publish workflow

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Flutter App (Web/Mobile)                 │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐  │
│  │  Chat    │ │  Alerts  │ │ Dashboard │ │   Profile    │  │
│  │ (RAG AI) │ │(Real-time│ │(Hazard Map│ │ (Emergency   │  │
│  │          │ │WebSocket)│ │           │ │  Contacts)   │  │
│  └────┬─────┘ └────┬─────┘ └─────┬─────┘ └──────────────┘  │
│       │             │             │                          │
│  ┌────▼─────────────▼─────────────▼──────────────────────┐  │
│  │           API Service (HTTP + WebSocket)               │  │
│  │           Base URL: http://127.0.0.1:8002              │  │
│  └────────────────────────┬──────────────────────────────┘  │
└───────────────────────────│──────────────────────────────────┘
                            │ REST API / WebSocket
┌───────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend (Port 8002)                 │
│                                                               │
│  /auth     /alerts    /rag/query    /knowledge    /sync       │
│  /monitor  /ws/alerts                                         │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  RAG Service (Phase 3)                   │ │
│  │  Query → Normalize → Curated Override → Retrieve        │ │
│  │        → Intent Classify → FAISS Rerank                 │ │
│  │        → Alert Inject → LLM Generate → Cache            │ │
│  └───────────────────────┬─────────────────────────────────┘ │
│                           │                                   │
│  ┌────────────┐  ┌────────▼────────┐  ┌──────────────────┐  │
│  │  SQLite    │  │ knowledge.sqlite │  │  FAISS Index     │  │
│  │  (alerts,  │  │  (400+ chunks,  │  │  (optional       │  │
│  │   users,   │  │   Urdu+English) │  │   semantic       │  │
│  │   sync)    │  │                 │  │   reranking)     │  │
│  └────────────┘  └─────────────────┘  └──────────────────┘  │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │           APScheduler — Alert Monitor (6h interval)     │ │
│  │   NDMA → PDMA KP → PMD → PDMA Punjab → ReliefWeb → OCHA│ │
│  └─────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │   Ollama (Local LLM)        │
              │   Model: llama3 / mistral   │
              │   Port: 11434               │
              │   Zero API cost, offline    │
              └─────────────────────────────┘
```

---

## ⚡ Quick Start

### Prerequisites
- Python 3.11 or 3.12
- Flutter 3.x SDK
- Git
- (Optional) Ollama for AI chat

### 1 — Clone the repo
```bash
git clone https://github.com/duaiqbal/Climate-Disaster.git
cd Climate-Disaster
```

### 2 — Backend setup
```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3 — Configure environment
```bash
# Copy the template
cp .env.example .env
# Edit .env with your settings (defaults work for local dev)
```

### 4 — Start backend
```bash
# Windows
python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload

# Mac/Linux
python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload
```
Backend runs at → http://127.0.0.1:8002  
API docs at → http://127.0.0.1:8002/docs

### 5 — Start Flutter app
```bash
cd ../app
flutter pub get
flutter run -d chrome --web-port 8080
```
App opens at → http://localhost:8080

### 6 — (Optional) Enable AI chat with Ollama
```bash
# Install Ollama from https://ollama.com
ollama pull llama3
ollama serve
# Then set LLM_PROVIDER=ollama in backend/.env
```

---

## 📖 Detailed Setup

### Backend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `development` | `development` or `production` |
| `SECRET_KEY` | dev-secret | JWT signing key — **change in production** |
| `ADMIN_API_KEY` | dev-key | Admin endpoint key — **change in production** |
| `DATABASE_URL` | SQLite in TEMP | SQLAlchemy DB URL |
| `LLM_PROVIDER` | `none` | `none` / `ollama` / `openai` / `groq` |
| `LLM_MODEL` | `llama3` | Model name for LLM provider |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Ollama/OpenAI-compatible base URL |
| `LLM_API_KEY` | *(empty)* | API key for OpenAI or Groq |
| `LLM_MAX_TOKENS` | `400` | Max tokens in LLM response |
| `LLM_MIN_CONFIDENCE` | `1` | Min retrieval hits before LLM is called |
| `MONITOR_ENABLED` | `1` | Enable alert scraping scheduler |
| `MONITOR_INTERVAL_HOURS` | `6` | How often to scrape alerts |
| `CORS_ORIGINS` | localhost:8080 | Comma-separated allowed CORS origins |
| `ACCESS_TOKEN_TTL` | `3600` | JWT access token TTL in seconds |
| `REFRESH_TOKEN_TTL` | `604800` | Refresh token TTL (7 days) |

### LLM Provider Options

**Option A — Ollama (recommended, free, offline)**
```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3
LLM_BASE_URL=http://localhost:11434/v1
```

**Option B — OpenAI**
```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

**Option C — Groq (fast, free tier)**
```env
LLM_PROVIDER=groq
LLM_MODEL=llama3-8b-8192
LLM_API_KEY=gsk_...
```

**Option D — No LLM (offline text retrieval only)**
```env
LLM_PROVIDER=none
```

### Build Knowledge Database (Optional)
The app ships with a pre-built `knowledge.sqlite`. To rebuild from PDFs:
```bash
cd pipeline
python run_pipeline.py
```

### Run Evaluation
```bash
cd evaluation
python retrieval_eval.py --k 5
```

---

## 📡 API Documentation

Full Swagger UI: `http://127.0.0.1:8002/docs`

### Auth Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, returns JWT tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Revoke refresh token |
| GET | `/auth/me` | Get current user profile |

### Alert Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/alerts` | List alerts (filter by district, severity, status, radius) |
| GET | `/alerts/{id}` | Get single alert with full provenance |
| POST | `/alerts` | Create alert (admin only) |
| PUT | `/alerts/{id}` | Update alert (admin only) |
| PATCH | `/alerts/{id}/transition` | Lifecycle transition (admin only) |
| DELETE | `/alerts/{id}` | Soft delete alert (admin only) |

**Alert filter params:** `district`, `province`, `hazard_type`, `severity`, `verification_status`, `active_only`, `lat`, `lon`, `radius_km`, `limit`, `offset`

### RAG / AI Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rag/query` | Ask AI chatbot a question |

**Request body:**
```json
{
  "question": "What to do during a flood?",
  "language": "en",
  "top_k": 5,
  "active_alert": {
    "title": "Flood Warning Chitral",
    "hazard_type": "flood",
    "severity": "HIGH"
  }
}
```

**Response:**
```json
{
  "answer": "During a flood, move to higher ground immediately...",
  "sources": [
    {
      "source_org": "NDMA",
      "doc_title": "Flood Situation Report 2023-24",
      "source_url": "https://ndma.gov.pk/...",
      "disaster_type": "flood",
      "phase": "during"
    }
  ],
  "confidence": "high",
  "provider_used": "ollama",
  "generation_used": true,
  "disaster_type": "flood",
  "phase": "during"
}
```

### Knowledge Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/knowledge/search?q=flood&language=en` | Search knowledge chunks |
| GET | `/knowledge/chunks` | List all chunks |
| GET | `/knowledge/meta` | Knowledge DB metadata |

### Sync Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sync/status` | Latest published package info |
| GET | `/sync/updates` | List all published versions |
| POST | `/sync/publish` | Publish new knowledge package (admin only) |

### Monitor Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/monitor/status` | Scheduler status + last run result |
| POST | `/monitor/run` | Manually trigger alert scraping (admin only) |

### WebSocket
```
ws://127.0.0.1:8002/ws/alerts
```
Receives real-time alert events when new alerts are scraped.

### Health
```
GET /health
→ { "status": "ok", "version": "2.0.0", "db": "sqlite", "env": "development" }
```

---

## 🤖 AI / RAG System

### How it works

```
User Query
    │
    ▼
1. Roman Urdu normalization (selab→flood, baarish→rain ...)
    │
    ▼
2. Curated override check (emergency contacts, go-bag → instant answer)
    │
    ▼
3. Keyword retrieval from knowledge.sqlite (400+ chunks)
   Filtered by: language + disaster_type + phase
    │
    ▼
4. FAISS semantic reranking (if index available)
    │
    ▼
5. Alert context injection (if active alert provided)
    │
    ▼
6. LLM generation (Ollama/OpenAI/Groq)
   Grounding-strict system prompt:
   - No facts outside retrieved chunks
   - No fabricated alerts
   - Source attribution required
    │
    ▼
7. Response cache (TTL: 5 min, skipped for alert-dependent queries)
    │
    ▼
Response with answer + sources + confidence + phase
```

### Retrieval Evaluation Results

| Language | Queries | P@5 | R@5 | MRR | F1 |
|----------|---------|-----|-----|-----|----|
| English | 14 | 1.000 | 1.000 | 1.000 | 1.000 |
| Urdu (اردو) | 6 | 0.980 | 0.980 | 0.990 | 0.980 |
| Roman Urdu | 7 | 0.943 | 0.943 | 0.971 | 0.943 |
| **Overall** | **27** | **0.981** | **0.981** | **0.990** | **0.981** |

### Knowledge Base
- **400+ chunks** from 13 official PDFs
- Sources: NDMA, PDMA KP, PMD
- Languages: English + Urdu translations
- Each chunk tagged with: `disaster_type`, `phase` (before/during/after), `source_org`, `source_url`

---

## 🧪 Testing

```bash
cd backend
python -m pytest tests/ -v
```

**122 tests across 5 test suites:**

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_auth.py` | 20 | JWT, registration, login, refresh, logout |
| `test_alerts.py` | 15 | CRUD, lifecycle, provenance, filtering |
| `test_knowledge_sync.py` | 15 | Knowledge search, sync endpoints, RAG shape |
| `test_phase2_alerts.py` | 18 | Multi-source, radius filter, WebSocket, haversine |
| `test_phase3_rag.py` | 34 | RAG curated, intent, alert-aware, Urdu, FAISS, cache |
| `test_phase1_regressions.py` | 20 | Port, SQL, schema, payload regressions |

All tests use **isolated in-memory SQLite** per test — no shared state.

---

## 📁 Project Structure

```
Climate-Disaster/
│
├── README.md                    ← This file
├── SETUP.md                     ← Detailed setup guide for team members
├── setup.ps1                    ← Windows one-click setup script
├── setup.sh                     ← Mac/Linux one-click setup script
│
├── backend/                     ← FastAPI Python backend
│   ├── main.py                  ← App entry point, lifespan, routers
│   ├── database.py              ← SQLAlchemy engine + session factory
│   ├── requirements.txt         ← Python dependencies
│   ├── .env.example             ← Environment variable template
│   │
│   ├── core/
│   │   ├── config.py            ← Settings (env vars, production safety)
│   │   ├── security.py          ← JWT, bcrypt, token helpers
│   │   ├── rate_limit.py        ← Rate limiting middleware
│   │   ├── scheduler.py         ← APScheduler (alert monitor)
│   │   └── ws_manager.py        ← WebSocket connection manager
│   │
│   ├── models/
│   │   └── db_models.py         ← SQLAlchemy ORM models
│   │
│   ├── routers/
│   │   ├── auth.py              ← /auth/* endpoints
│   │   ├── alerts.py            ← /alerts/* endpoints
│   │   ├── knowledge.py         ← /knowledge/* endpoints
│   │   ├── rag.py               ← /rag/query endpoint
│   │   ├── sync.py              ← /sync/* endpoints
│   │   ├── monitor.py           ← /monitor/* endpoints
│   │   └── ws.py                ← WebSocket /ws/alerts
│   │
│   ├── services/
│   │   ├── rag_service.py       ← Full RAG pipeline (Phase 3)
│   │   └── faiss_service.py     ← FAISS vector index (optional)
│   │
│   └── tests/
│       ├── conftest.py          ← Isolated test fixtures
│       ├── test_auth.py
│       ├── test_alerts.py
│       ├── test_knowledge_sync.py
│       ├── test_phase1_regressions.py
│       ├── test_phase2_alerts.py
│       └── test_phase3_rag.py
│
├── app/                         ← Flutter application
│   ├── pubspec.yaml             ← Flutter dependencies
│   ├── lib/
│   │   ├── main.dart            ← App entry point
│   │   ├── core/
│   │   │   ├── services/        ← API service, disaster repository
│   │   │   ├── theme/           ← Colors, text styles
│   │   │   ├── localization/    ← English/Urdu/Roman Urdu translations
│   │   │   ├── retrieval/       ← Offline keyword retrieval engine
│   │   │   ├── rules_engine/    ← Offline response builder
│   │   │   └── local_db/        ← SQLite local storage
│   │   └── features/
│   │       ├── chat/            ← AI chatbot screen
│   │       ├── alerts/          ← Real-time alerts screen
│   │       ├── dashboard/       ← Risk dashboard + hazard map
│   │       ├── profile/         ← User profile + emergency contacts
│   │       └── auth/            ← Login/register screens
│   └── assets/
│       ├── images/              ← App images
│       └── fonts/               ← Custom fonts
│
├── pipeline/                    ← Data pipeline (builds knowledge.sqlite)
│   ├── run_pipeline.py          ← Main pipeline runner
│   ├── rag/
│   │   ├── chunk.py             ← PDF chunking + classification
│   │   └── translate_urdu.py    ← Urdu translation
│   └── package_builder/
│       └── build_sqlite.py      ← Builds knowledge.sqlite
│
├── fetchers/                    ← Alert scraping
│   └── official_alert_monitor.py ← Multi-source alert scraper
│
├── evaluation/                  ← Retrieval evaluation
│   ├── retrieval_eval.py        ← P@K, R@K, MRR metrics
│   └── ground_truth_eval.json   ← 27 annotated queries
│
├── offline_package/             ← Pre-built knowledge.sqlite ships here
│   └── knowledge.sqlite
│
└── data/
    └── raw/                     ← Source PDFs (NDMA, PDMA KP docs)
```

---

## 🛠️ Common Issues & Fixes

### Backend won't start
```bash
# Check Python version (need 3.11+)
python --version

# Reinstall dependencies
pip install -r requirements.txt

# Check port not in use
netstat -ano | findstr :8002
```

### Flutter CORS error
Make sure backend `.env` has:
```env
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

### AI chat returns "insufficient evidence"
- `LLM_PROVIDER=none` means no LLM — retrieval-only mode
- Set `LLM_PROVIDER=ollama` and start Ollama: `ollama serve`
- Or set `LLM_MIN_CONFIDENCE=1` (already default)

### knowledge.sqlite not found
```bash
cd pipeline
python run_pipeline.py
```

### Tests failing
```bash
# Always run from backend/ directory
cd backend
python -m pytest tests/ -v
```

---

## 👥 Team & Contribution

**Project:**  
**Supervisor:** Muhammad Huzaifah 

### Team Members
| Name | Role |
|------|------|
| Dua Iqbal | Lead Developer — Backend, RAG, Alerts |
| Tooba  | Flutter App Development |
| [Tooba and Simrah ] | Data Pipeline, Knowledge Base |
| [Hafsa and Manahil] | UI/UX,  |Kiran: Testing 

### Contributing
1. Fork the repo
2. Create feature branch: `git checkout -b feature/your-feature`
3. Run tests: `cd backend && python -m pytest tests/ -v`
4. Commit: `git commit -m "feat: your feature description"`
5. Push: `git push origin feature/your-feature`
6. Open Pull Request

---

## 📞 Emergency Contacts (Built into App)

| Service | Number |
|---------|--------|
| Rescue KP | 1122 |
| PDMA KP | 051-9222373 |
| NDMA | 051-9246136 |
| PMD Weather | 051-9250363 |
| Edhi Foundation | 115 |
| AKHS Chitral | 0943-412093 |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ for the people of Chitral, KP, Pakistan<br/>
  Data sources: NDMA Pakistan, PDMA KP, Pakistan Meteorological Department
</p>
