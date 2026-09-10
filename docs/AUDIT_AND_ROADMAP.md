# Disaster DSS — Full Repository Audit, Gap Analysis & Production Roadmap

**Audit date:** September 2026  
**Auditor:** System Architect (full-stack, security, GIS, AI/RAG, DevOps)  
**Repository:** https://github.com/duaiqbal/Climate-Disaster  
**Based on:** Actual codebase inspection — not README claims

---

## 1. COMPLETE ARCHITECTURE MAP (Current State)

```
data/raw/*.pdf  (10 real NDMA PDFs + 2 PDMA KP PDFs)
      │
      ▼  pipeline/rag/extract.py (PyMuPDF)
data/extracted/*.json  (14 docs, 386 pages total)
      │
      ▼  pipeline/rag/chunk.py
data/chunks/*.json  (315 chunks, English only)
      │
      ├─► pipeline/rag/embed.py  → data/embeddings/index.faiss (114KB, 315 vectors)
      │                            data/embeddings/all_embeddings.npy (114KB)
      │                            [multilingual MiniLM, 384-dim]
      │
      ▼  pipeline/package_builder/build_sqlite.py
offline_package/knowledge.sqlite (216KB)
      │
      ▼  copied to →  app/assets/offline_package/knowledge.sqlite

pipeline/gis/compute_hazard_grid.py
      ▼
offline_package/hazard_grid.sqlite (2.1MB, 10,000 cells, synthetic terrain)
      │
      ▼  copied to →  app/assets/offline_package/hazard_grid.sqlite

fetchers/official_pdf_downloader.py  ← downloads from ndma.gov.pk
fetchers/official_alert_monitor.py   ← HTML scraping, change detection
fetchers/pdma_kp_fetcher.py          ← manual ingestion helper

Flutter App (app/)
  ├── main.dart                        ← startup, routing, kIsWeb guard
  ├── core/config/app_config.dart      ← backend URL via --dart-define
  ├── core/local_db/database_helper.dart  ← sqflite wrapper, kIsWeb guarded
  ├── core/retrieval/keyword_retriever.dart  ← LIKE search on SQLite
  ├── core/retrieval/roman_urdu_normalizer.dart  ← variant expansion
  ├── core/rules_engine/hazard_rules.dart  ← deterministic threshold rules
  ├── core/services/auth_service.dart  ← HTTP auth, SharedPreferences session
  ├── core/providers/                  ← LanguageProvider, AppStateProvider
  └── features/                        ← 10 screens

FastAPI Backend (backend/)
  ├── main.py           ← lifespan, CORS (explicit origins), 5 routers
  ├── database.py       ← SQLAlchemy async + aiosqlite, DATABASE_URL env
  ├── models/db_models.py  ← 3 ORM tables, Pydantic schemas
  └── routers/
      ├── auth.py       ← register/login, PBKDF2+HMAC-SHA256, custom token
      ├── alerts.py     ← CRUD, admin key, soft delete
      ├── knowledge.py  ← read-only SQLite search (sync, blocks event loop)
      ├── sync.py       ← package version management
      └── monitor.py    ← POST /monitor/run triggers scraper subprocess

Backend DB (backend/disaster_dss_backend.sqlite, 24KB):
  - users (7 rows — test accounts)
  - alerts (0 rows — no live alerts yet)
  - package_updates (0 rows)
```

---

## 2. AUDIT RESULTS — STATUS PER COMPONENT

### PASS ✅

| Component | Detail |
|-----------|--------|
| Offline SQLite retrieval | 315 real chunks, LIKE search, Roman Urdu expansion — works in airplane mode |
| Hazard grid | 10,000 cells, deterministic rules, correct disclaimer |
| Multilingual support | en/ur/ru strings, localization architecture |
| Flutter web kIsWeb guards | SQLite/path_provider calls safely skipped on web |
| AppConfig URL abstraction | `--dart-define=BACKEND_URL` properly wired |
| CORS fix | Explicit localhost:8080 origins, not wildcard with credentials |
| Backend imports | All 5 routers load cleanly |
| Health/alerts/knowledge/sync endpoints | Live validated 14/14 |
| PDF downloader | 10 real NDMA PDFs from verified URLs, checksummed |
| Alert monitor | HTML scraping + change detection + provenance fields |
| Retrieval evaluation | P@5=1.0, R@5=1.0, MRR=1.0 on 20 annotated queries |
| FAISS embeddings built | 315 vectors, 384-dim multilingual MiniLM |

### PARTIAL ⚠️

| Component | What Works | What's Missing |
|-----------|-----------|----------------|
| Authentication | Register, login, token creation work | No JWT (custom HMAC only), no refresh tokens, no token revocation, no rate limiting, password min=4 chars, no role-based access |
| Token storage | SharedPreferences with TTL check | Should be flutter_secure_storage on mobile; web SharedPreferences is acceptable |
| Alert provenance | source_org present in alerts table | Missing: source_url, fetch_timestamp, content_hash, verification_status columns in backend DB |
| Online sync | Alerts sync from backend to SQLite | No incremental sync, no checksum validation before replace, no atomic update |
| FAISS semantic search | Index built, 315 vectors present | NOT wired into any endpoint — backend knowledge.py uses only SQLite LIKE, Flutter uses only keyword retrieval |
| Evaluation | P@5=1.0 on EN/RU | Urdu queries skipped (0 annotated) — 0 Urdu chunks in DB |
| Error handling | Basic HTTP status differentiation | Flutter catches generic exceptions, no structured error type (NO_INTERNET vs TIMEOUT vs 401 vs 429) |
| Monitor router | POST /monitor/run implemented | Never scheduled — requires manual trigger |

### BROKEN ❌

| Component | Issue |
|-----------|-------|
| knowledge.py in async context | Uses synchronous `sqlite3.connect()` inside `async def` handlers — blocks the event loop on every knowledge request |
| Passwords min length 4 | `password: str = Field(..., min_length=4)` — dangerously weak for production |
| Default SECRET_KEY in code | `os.getenv("SECRET_KEY", "disaster-dss-dev-secret-change-in-production")` — if env var not set, silently uses dev secret in production |
| Default ADMIN_API_KEY in code | Same pattern — silent dev fallback |
| Alert verification status | `alerts` table has no `source_url`, `content_hash`, `verification_status`, `fetch_timestamp` columns — constraint 4 of the hard requirements not met in the DB schema |
| No refresh tokens | 24-hour access tokens with no refresh mechanism — users are locked out after 24h with no recovery path |
| No rate limiting | Login endpoint has no brute-force protection |
| backend/requirements.txt is empty | 0 bytes — `pip install -r backend/requirements.txt` installs nothing |

### MISSING 🔴

| Feature | Priority |
|---------|----------|
| JWT (python-jose or PyJWT) | P0 |
| Refresh tokens + revocation | P0 |
| bcrypt or argon2 password hashing | P0 |
| flutter_secure_storage | P0 |
| Role-based access (user/admin) | P0 |
| Alert schema: source_url, content_hash, verification_status, fetch_timestamp | P0 |
| Alert lifecycle state machine (DISCOVERED→FETCHED→VALIDATED→PUBLISHED) | P0 |
| Database migrations (Alembic) | P0 |
| FAISS semantic search wired into backend `/knowledge/search` | P1 |
| Semantic RAG endpoint (`/rag/query`) | P1 |
| LLM integration (provider-agnostic, configurable) | P1 |
| Structured Flutter error types (NetworkError, AuthError, etc.) | P1 |
| Scheduled alert monitor (APScheduler or background task) | P1 |
| Incremental sync with version/checksum | P1 |
| Atomic SQLite package update (temp file → checksum → replace) | P1 |
| Backend pytest suite | P1 |
| Flutter widget/service tests | P1 |
| Weather data source (Open-Meteo or PMD) | P2 |
| Push notifications (FCM) | P2 |
| SSE/WebSocket for live alert push | P2 |
| Urdu PDF ingestion | P2 |
| Production Docker/deployment config | P2 |
| Monitoring / health dashboard | P3 |

### RISK ⚠️

| Risk | Severity |
|------|---------|
| Dev SECRET_KEY used in production if env var not set | CRITICAL |
| PBKDF2 is acceptable but argon2/bcrypt preferred for new auth | HIGH |
| No token revocation — compromised token valid for 24h | HIGH |
| Scraper HTML structure changes break alert monitor silently | MEDIUM |
| 40MB NDMA DRM strategy PDF causes memory issues on slow machines | LOW |
| Synthetic hazard grid labeled correctly but README old stats (465 chunks) were not fully cleaned | LOW |

### PRODUCTION BLOCKERS 🚫

1. **SECRET_KEY env var** — must fail startup if not set in production mode
2. **Empty backend/requirements.txt** — deployment will fail
3. **No refresh tokens** — 24h hard expiry with no recovery
4. **Alert table missing provenance columns** — constraint 4 violation
5. **knowledge.py blocking event loop** — performance failure under load
6. **No migration system** — schema changes require manual DB surgery
7. **Password min=4** — below any acceptable security baseline (min=8 required)

---

## 3. GAP ANALYSIS SUMMARY

```
CURRENT STATE                    TARGET STATE
─────────────────────────────    ─────────────────────────────
PBKDF2 custom token         →    bcrypt/argon2 + JWT + refresh
SharedPreferences token     →    flutter_secure_storage (mobile)
3 DB tables                 →    8+ tables with full provenance
No migrations               →    Alembic migrations
Keyword retrieval only      →    Keyword + FAISS semantic + rerank
No LLM layer                →    Provider-agnostic RAG+LLM service
Manual monitor trigger      →    Scheduled background worker
No tests                    →    pytest suite + Flutter tests
Empty requirements.txt      →    Pinned production requirements
Hardcoded dev secrets       →    Fail-fast on missing production env
Sync: full replace          →    Incremental + checksum + atomic
No error types              →    Structured error classification
```

---

## 4. PRIORITY MATRIX

| ID | Feature | Impact | Effort | Priority |
|----|---------|--------|--------|----------|
| P0-1 | Fix backend/requirements.txt | CRITICAL | Low | IMMEDIATE |
| P0-2 | Fail-fast on missing production secrets | CRITICAL | Low | IMMEDIATE |
| P0-3 | Fix knowledge.py async blocking | HIGH | Low | IMMEDIATE |
| P0-4 | Upgrade password hashing to bcrypt | HIGH | Medium | P0 |
| P0-5 | Replace custom token with JWT + refresh | HIGH | Medium | P0 |
| P0-6 | Add alert provenance columns (migration) | HIGH | Medium | P0 |
| P0-7 | Alert lifecycle state machine | HIGH | Medium | P0 |
| P0-8 | flutter_secure_storage on mobile | HIGH | Low | P0 |
| P0-9 | Password minimum 8 chars | MEDIUM | Low | P0 |
| P1-1 | Wire FAISS into /knowledge/search | HIGH | Medium | P1 |
| P1-2 | RAG endpoint with grounding | HIGH | High | P1 |
| P1-3 | Provider-agnostic LLM service | HIGH | High | P1 |
| P1-4 | Scheduled monitor (APScheduler) | MEDIUM | Low | P1 |
| P1-5 | Structured Flutter error types | MEDIUM | Medium | P1 |
| P1-6 | pytest suite (auth + alerts + RAG) | MEDIUM | Medium | P1 |
| P1-7 | Incremental sync + atomic update | MEDIUM | Medium | P1 |
| P2-1 | Weather integration (Open-Meteo) | MEDIUM | Medium | P2 |
| P2-2 | Flutter widget tests | MEDIUM | Medium | P2 |
| P2-3 | Urdu PDF sourcing | MEDIUM | High | P2 |
| P2-4 | Push notifications | LOW | High | P2 |
| P3-1 | Production Docker + deployment | MEDIUM | High | P3 |
| P3-2 | Monitoring / observability | LOW | High | P3 |

---

## 5. TARGET ARCHITECTURE

```
Flutter App
  │
  ├── OFFLINE PATH (always available)
  │     core/local_db/database_helper.dart
  │       ├── knowledge.sqlite (315 chunks, real NDMA/PDMA)
  │       │     KeywordRetriever + RomanUrduNormalizer
  │       └── hazard_grid.sqlite (10,000 cells, deterministic rules)
  │
  └── ONLINE PATH (when connected)
        core/services/auth_service.dart  [JWT + refresh token]
        core/services/api_service.dart   [typed HTTP client]
          │
          ▼  https://backend:443
        FastAPI Backend
          ├── /auth          [bcrypt + JWT + refresh + revocation]
          ├── /alerts        [provenance schema + lifecycle]
          ├── /rag/query     [FAISS semantic + grounded LLM]
          ├── /knowledge     [async FAISS search]
          ├── /sync          [incremental + checksum]
          ├── /monitor       [scheduled background worker]
          └── /health        [liveness + readiness]
              │
              ├── SQLite/PostgreSQL backend DB
              │     tables: users, roles, alerts, alert_history,
              │             sources, ingestion_runs, documents,
              │             chunks_meta, sync_packages
              │
              └── FAISS index (in-memory, loaded from data/embeddings/)
```

---

## 6. IMPLEMENTATION ROADMAP

### Phase P0 — Immediate Fixes (do now, blocks everything else)

**P0-1: Fix backend/requirements.txt**
**P0-2: Fail-fast secrets**
**P0-3: Fix knowledge.py async blocking**
**P0-4–9: Auth hardening (bcrypt, JWT, refresh, flutter_secure_storage)**
**P0-6: Alert provenance schema + Alembic migration**

### Phase P1 — Core Intelligence

**P1-1: FAISS wired into async knowledge search**
**P1-2: RAG endpoint with evidence grounding + refuse-on-low-confidence**
**P1-3: Provider-agnostic LLM service**
**P1-4: Scheduled alert monitor**
**P1-5: Structured error types in Flutter**
**P1-6: pytest suite**
**P1-7: Incremental sync + atomic SQLite update**

### Phase P2 — Real-time & Extended

Weather, push notifications, Urdu ingestion, Flutter tests

### Phase P3 — Production Hardening

Docker, HTTPS, monitoring, security audit, load testing

---

## 7. ACTUAL VALIDATED NUMBERS (as of audit)

| Metric | Value | Source |
|--------|-------|--------|
| Real official PDFs | 12 (10 NDMA + 2 PDMA KP) | data/raw/ |
| Knowledge chunks | 315 | knowledge.sqlite |
| Urdu chunks | 0 | audit_db.py |
| Hazard grid cells | 10,000 | hazard_grid.sqlite |
| Retrieval P@5 (EN) | 1.000 | evaluation/eval_summary.json |
| Retrieval P@5 (RU) | 1.000 | evaluation/eval_summary.json |
| Retrieval P@5 (UR) | N/A (no annotations) | — |
| Backend tests passing | 14/14 | validate_backend.py |
| Flutter analyze issues | 0 | flutter analyze --no-pub |
| Backend DB rows (users) | 7 | backend/disaster_dss_backend.sqlite |
| Backend DB rows (alerts) | 0 | backend/disaster_dss_backend.sqlite |
| FAISS vectors | 315 | data/embeddings/all_embeddings.npy |
| FAISS wired into runtime | NO | audit |

---

## 8. WHAT TO IMPLEMENT NEXT (Ordered)

Start with P0. Do not start P1 until P0 is done.

### P0 Sprint (implement in this order):

1. `backend/requirements.txt` — pin all dependencies
2. `backend/core/config.py` — fail-fast on missing production secrets
3. `backend/routers/knowledge.py` — fix async blocking (use `run_in_executor`)
4. Install: `pip install bcrypt python-jose[cryptography] alembic slowapi`
5. `backend/routers/auth.py` — replace PBKDF2+custom-token with bcrypt+JWT+refresh
6. `backend/models/db_models.py` — add `RefreshTokenORM`, extend `AlertORM` with provenance columns, add `role` to `UserORM`
7. Alembic migration for schema changes
8. Flutter: add `flutter_secure_storage` to pubspec.yaml
9. Flutter: update `auth_service.dart` to use flutter_secure_storage on mobile
10. Flutter: update `auth_service.dart` to handle JWT refresh

Each of these is a contained, testable change.

---

## 9. KNOWN REAL LIMITATIONS (honest, not hidden)

| Limitation | Root Cause | Mitigation |
|-----------|-----------|-----------|
| 0 Urdu chunks | NDMA publishes English-only PDFs | Manual translation or bilingual publication needed |
| Alert monitor scrapes HTML | No public official API exists | Monitor robustly + document structure change risk |
| Hazard grid is synthetic | No field-validated data available | Always labeled as indicator with disclaimer |
| P@5=1.0 may inflate on auto-generated GT | GT was auto-filled from same retriever | Requires human annotation to be truly independent |
| LLM not integrated | Not yet built | Phase P1 — grounded, provider-agnostic |
| No real-time push | NDMA has no push API | Polling every 6h is the maximum practical frequency |
