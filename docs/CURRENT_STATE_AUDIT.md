# ChitralSafe / Disaster DSS — Current State Audit

**Audit Date:** 2026-09-14  
**Auditor:** Kiro (automated code inspection — no assumptions, citations for every claim)  
**Scope:** Full codebase as of commit `b8a255e` (HEAD → master)  
**Instruction:** Read-only audit. No code was modified.

---

## EXECUTIVE SUMMARY

1. **Real-time alerts: Partially implemented.** The APScheduler and `fetchers/official_alert_monitor.py` are code-complete and will POST new alerts to the backend DB every 6 hours. The WebSocket broadcast path (`ws_manager.py`, `/ws/alerts`) is implemented. The Flutter `AlertService` connects to the WebSocket with HTTP-polling fallback. However the `monitor.py` router default URL points to port `8001` while the app runs on `8002`, and the fetcher does not set `source_url` or `verification_status` as top-level JSON fields in its POST payload.

2. **Chatbot / RAG: Scaffolded, mostly curated — not true RAG at runtime.** The `/rag/query` endpoint exists and is called from Flutter. At runtime it first hits a hardcoded Python dictionary (`_get_curated_answer()` in `rag_service.py`) that returns canned answers. Only if no keyword match occurs does it fall through to actual DB chunk retrieval. The LLM (Ollama/llama3) path is configured in `.env` but is not operational (Ollama not installed) and falls through to `_clean_chunks()` sentence extraction. No FAISS/vector retrieval occurs at runtime anywhere in the request path.

3. **Flutter offline retrieval is broken.** `retrieval_engine.dart` contains a SQL query that references non-existent tables (`knowledge`, `chunk_metadata`) and non-existent columns (`text`, `source_title`, `publication_date`). The actual `knowledge.sqlite` has a single `chunks` table with a `chunk_text` column. This code will throw a SQL exception at runtime on mobile. The Dart files themselves carry the comment "UNVERIFIED DRAFT — not run/tested against a real Flutter build."

4. **All 315 knowledge chunks are English-only.** `offline_package/manifest.json` confirms `lang_ur=0, lang_ru=0`. Urdu and Roman Urdu queries on-device will either return no results or must fall through to the backend curated KB. The retrieval evaluation file has 6 Urdu queries and 7 Roman Urdu queries, all with `relevant_chunk_ids: []` for Urdu (empty because nothing was found).

5. **The alert lifecycle state machine is fully implemented on the backend** (`DISCOVERED → FETCHED → VALIDATED → OFFICIAL-VERIFIED → PUBLISHED → EXPIRED`). It is written to and read from the DB via the `PUT /alerts/{id}/transition` endpoint. Flutter does not use lifecycle states in display — it only filters `active_only=true`.

6. **Default run port is 8002** (per `.env` `BACKEND_URL`, `scheduler.py`, and `alert_service.dart`). The `main.py` docstring still says `--port 8001` and `monitor.py` router's `_run_fetcher()` defaults to `http://127.0.0.1:8001` — this is a live bug: manual monitor trigger will POST to wrong port.

---

## PART A — BACKEND AUDIT

### A1. `backend/main.py` — Routers, Lifespan, Scheduler

**File:** `backend/main.py`  
**APP_VERSION:** `"2.0.0"`

**Routers mounted:**

| Import alias | Prefix | Source file |
|---|---|---|
| `auth.router` | `/auth` | `backend/routers/auth.py` |
| `alerts.router` | `/alerts` | `backend/routers/alerts.py` |
| `knowledge.router` | `/knowledge` | `backend/routers/knowledge.py` |
| `rag_router.router` | `/rag` | `backend/routers/rag.py` |
| `sync.router` | `/sync` | `backend/routers/sync.py` |
| `monitor.router` | `/monitor` | `backend/routers/monitor.py` |
| `ws_router.router` | (no prefix) | `backend/routers/ws.py` |

**Lifespan (`@asynccontextmanager`):**
1. `await init_db()` — creates all tables
2. `start_scheduler()` — APScheduler (from `core/scheduler.py`)
3. `asyncio.create_task(_ws_ping_loop())` — sends heartbeat ping to all WebSocket clients every 30 seconds
4. Shutdown: `stop_scheduler()`

**Middleware:** `CORSMiddleware` (origins from `settings.cors_origins`), `RateLimitMiddleware`

**Routes defined in `main.py` itself:**
- `GET /health` → `HealthResponse{status, version, db, env, timestamp}`
- `GET /` → JSON `{service, version, env, docs}`
- `@app.exception_handler(404)` → JSON `{detail:"Not found"}`
- `@app.exception_handler(500)` → JSON `{detail:"Internal server error."}`

**Default run command (from `main.py` docstring):**  
`python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload`  
⚠️ **DISCREPANCY:** The `.env` file sets `BACKEND_URL=http://127.0.0.1:8002` and `alert_service.dart` connects to `8002`. The docstring port `8001` is outdated.

---

### A2. `backend/database.py` and `backend/models/db_models.py`

**File:** `backend/database.py`

- Async SQLite engine via `sqlalchemy.ext.asyncio.create_async_engine`
- `DATABASE_URL` default: `sqlite+aiosqlite:///{TEMP}/disaster_dss_backend.sqlite` (Windows `%TEMP%` folder)
- `async def init_db()`: calls `Base.metadata.create_all` on startup

**File:** `backend/models/db_models.py`

**All ORM tables and fields (complete):**

#### `users`
| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK autoincrement | |
| `name` | String(120) | NOT NULL |
| `email` | String(255) | UNIQUE, NOT NULL |
| `hashed_password` | String(255) | NOT NULL |
| `role` | String(16) | default="user" |
| `district` | String(64) | nullable |
| `language` | String(8) | default="en" |
| `is_active` | Boolean | default=True |
| `created_at` | DateTime(tz) | server_default=now() |
| `updated_at` | DateTime(tz) | server_default=now(), onupdate=now() |

#### `refresh_tokens`
| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | Integer | FK→users.id CASCADE DELETE |
| `token_hash` | String(128) | UNIQUE (SHA-256 of opaque token) |
| `issued_at` | DateTime(tz) | |
| `expires_at` | DateTime(tz) | NOT NULL |
| `revoked` | Boolean | default=False |
| `revoked_at` | DateTime(tz) | nullable |
| `user_agent` | String(255) | nullable |
| `ip_address` | String(64) | nullable |

#### `sources`
| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `source_id` | String(64) | UNIQUE, uuid4[:12] |
| `org` | String(64) | NOT NULL |
| `doc_title` | String(255) | nullable |
| `source_url` | String(512) | NOT NULL |
| `fetched_at` | DateTime(tz) | |
| `checksum_sha256` | String(64) | nullable |
| `content_type` | String(64) | nullable |
| `language` | String(8) | default="en" |
| `is_active` | Boolean | default=True |
| `created_at` | DateTime(tz) | |

#### `ingestion_runs`
| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `run_id` | String(64) | UNIQUE, uuid4[:12] |
| `started_at` | DateTime(tz) | |
| `finished_at` | DateTime(tz) | nullable |
| `trigger` | String(32) | default="scheduled" |
| `status` | String(16) | default="running" |
| `sources_checked` | Integer | default=0 |
| `new_found` | Integer | default=0 |
| `alerts_created` | Integer | default=0 |
| `alerts_skipped` | Integer | default=0 |
| `error_message` | Text | nullable |
| `runner_version` | String(32) | nullable |

#### `alerts`
| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `alert_id` | String(64) | UNIQUE, uuid4[:12] |
| `title` | String(255) | NOT NULL |
| `body` | Text | NOT NULL |
| `hazard_type` | String(32) | values: flood/flash_flood/landslide/glof/other/general |
| `severity` | String(16) | values: LOW/MEDIUM/HIGH/EXTREME |
| `issued_at` | DateTime(tz) | NOT NULL |
| `published_at` | DateTime(tz) | nullable, set when status→PUBLISHED |
| `fetch_timestamp` | DateTime(tz) | nullable |
| `updated_at` | DateTime(tz) | nullable |
| `expires_at` | DateTime(tz) | nullable |
| `source_org` | String(64) | NOT NULL |
| `source_url` | String(512) | nullable |
| `content_hash` | String(64) | nullable (SHA-256 of body) |
| `verification_status` | String(32) | default="DISCOVERED"; values: DISCOVERED/FETCHED/VALIDATED/OFFICIAL-VERIFIED/PUBLISHED/EXPIRED |
| `source_id` | String(64) | FK→sources.source_id SET NULL |
| `ingestion_run_id` | String(64) | FK→ingestion_runs.run_id SET NULL |
| `district` | String(64) | nullable |
| `province` | String(64) | nullable |
| `latitude` | Float | nullable |
| `longitude` | Float | nullable |
| `language` | String(8) | default="en" |
| `is_active` | Boolean | default=True |
| `created_at` | DateTime(tz) | |

**Alert questions answered:**
- ✅ Alert model exists with `hazard_type`, `severity`, `issued_at`, `expires_at`, `source_org/source_url`
- ✅ Geographic location: `district` (String), `province` (String), `latitude` (Float), `longitude` (Float). No link to `hazard_grid` coordinate scheme at the ORM level.
- ✅ Lifecycle field `verification_status` exists. It is read in `GET /alerts?verification_status=` filter, written in `POST /alerts`, `PUT /alerts/{id}`, and `POST /alerts/{id}/transition`. It is not purely cosmetic.
- ✅ Deduplicate key: `content_hash` (SHA-256 of body). `alert_id` (UUID) also unique but generated fresh each insert. The fetcher checks `seen_urls` in a state JSON file, not the `content_hash`.

#### `alert_history`
| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `alert_db_id` | Integer | FK→alerts.id CASCADE DELETE |
| `changed_at` | DateTime(tz) | |
| `changed_by` | String(64) | nullable |
| `field_name` | String(64) | NOT NULL |
| `old_value` | Text | nullable |
| `new_value` | Text | nullable |
| `action` | String(32) | created/updated/transitioned/deleted |

#### `package_updates`
| Field | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `version` | String(32) | |
| `built_at` | DateTime(tz) | |
| `chunk_count` | Integer | default=0 |
| `knowledge_checksum` | String(64) | nullable |
| `hazard_checksum` | String(64) | nullable |
| `release_notes` | Text | nullable |
| `created_at` | DateTime(tz) | |

---

### A3. `backend/routers/` — All Endpoints

#### `backend/routers/alerts.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/alerts` | None | List with filters: `district` (ilike), `hazard_type` (exact), `severity` (upper), `language`, `verification_status`, `active_only` (default True), `limit` (1–200, default 50), `offset` |
| GET | `/alerts/{alert_id}` | None | Detail with full `alert_history` list |
| POST | `/alerts` | X-Admin-Key | Create; SHA-256 hashes body; appends history action="created"; broadcasts to WebSocket via `await ws_manager.broadcast_alert()` |
| PUT | `/alerts/{alert_id}` | X-Admin-Key | Update all fields; appends history action="updated" |
| POST | `/alerts/{alert_id}/transition` | X-Admin-Key | Advance lifecycle state; PUBLISHED sets `published_at`; EXPIRED sets `is_active=False` |
| DELETE | `/alerts/{alert_id}` | X-Admin-Key | Soft delete: `is_active=False`; returns 204 |

**Location filtering on GET /alerts:** Only `district` (string ilike `%value%`). No radius search, no lat/lon bounding box, no link to `hazard_grid`. **Result: location filtering exists but is district-name string matching only.**

#### `backend/routers/auth.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | None | Create user; 409 on duplicate email |
| POST | `/auth/login` | None | Returns JWT access token + opaque refresh token |
| POST | `/auth/refresh` | None (refresh token in body) | Token rotation; revokes old |
| POST | `/auth/logout` | None | Revokes refresh token; always 204 |
| GET | `/auth/me` | JWT Bearer | Returns `UserResponse` |

#### `backend/routers/knowledge.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/knowledge/search?q=&language=en&limit=10` | None | LIKE search; returns scored chunks |
| GET | `/knowledge/chunks?language=en&limit=20&offset=0` | None | Paginated chunk list |
| GET | `/knowledge/meta` | None | `package_meta` key-value pairs |

**Exact SQL used for search** (from `_do_search`, `backend/routers/knowledge.py`):
```sql
SELECT chunk_id, source_org, doc_title, pub_date, language,
       page_num, chunk_text, keywords, evidence_level, char_count,
       COALESCE(source_url, '') AS source_url,
       (CASE WHEN chunk_text LIKE ? THEN 1 ELSE 0 END + ...) AS score
FROM chunks
WHERE language = ? AND (chunk_text LIKE ? OR keywords LIKE ? ...)
ORDER BY score DESC LIMIT ?
```
Retrieval method: **keyword LIKE only**. No vector/semantic search at runtime.

#### `backend/routers/rag.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/rag/query` | None | Body: `{question, language="en", top_k=5}` |

**Flow:** calls `_do_search` → `query_rag(question, chunks, language)` → `RAGQueryResponse`

**Does any router call an LLM?** Yes — `backend/services/rag_service.py::query_rag()` can call `_call_ollama()`, `_call_openai()`, or `_call_groq()`. But only if `LLM_PROVIDER != "none"` AND steps 1 (curated KB match) and 2 (insufficient score check) are both passed. At current `.env` settings (`LLM_PROVIDER=ollama`), it would attempt to call `http://localhost:11434/v1` — which will fail if Ollama is not installed, falling through to `_clean_chunks()` extraction.

**Online vs. offline LLM decision:** entirely server-side. No connectivity flag from Flutter. The fallback is a `try/except Exception` around the OpenAI client call in `_call_ollama()` returning `""` on error.

#### `backend/routers/monitor.py`

**Does `/monitor` exist with `/monitor/run` and `/monitor/status`?** ✅ Confirmed.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/monitor/status` | None | Returns `{scheduler_running, next_scheduled_run, last_run_status, last_run_at, seen_url_count, fetcher_exists}` |
| POST | `/monitor/run` | X-Admin-Key | Triggers fetcher immediately; timeout=120s; default `BACKEND_URL=http://127.0.0.1:8001` |
| POST | `/monitor/run-dry` | X-Admin-Key | Same but passes `--dry-run` to fetcher |

⚠️ **BUG:** `monitor.py` default `BACKEND_URL = http://127.0.0.1:8001` but the backend runs on `8002`. Manual `/monitor/run` will POST new alerts to port 8001 (which is not listening). The scheduled APScheduler job in `scheduler.py` correctly uses `http://127.0.0.1:8002`.

#### `backend/routers/sync.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/sync/status` | None | Latest `PackageUpdateORM` row or null |
| GET | `/sync/updates` | None | Last 20 package versions |
| POST | `/sync/publish` | X-Admin-Key | Records new offline package version |

#### `backend/routers/ws.py`

| Type | Path | Auth | Description |
|---|---|---|---|
| WebSocket | `/ws/alerts` | None | Persistent connection; server pushes `{type:"new_alert"|"ping"|"monitor_done"}` |

**Does any router perform vector/semantic (FAISS) search?** ❌ No. All retrieval is keyword LIKE search. `embed.py` generates a FAISS index at `data/embeddings/index.faiss` during pipeline execution, but this file is **not loaded or used** by any backend router or the Flutter app at runtime.

---

### A4. Files Outside `routers/` Related to LLM / Scheduler

**LLM-related files found:**
- `backend/services/rag_service.py` — contains all LLM provider implementations
- No `llm_service.py`, `generation.py`, `ollama_client.py` found as separate files

**Scheduler file:**
- `backend/core/scheduler.py` — APScheduler `AsyncIOScheduler` (see §A1)

**`requirements.txt` coverage check:**
- `apscheduler==3.10.4` ✅ listed
- `openai==1.35.3` ✅ listed (used for Ollama/Groq via OpenAI-compatible API)
- `faiss-cpu` ❌ **NOT in `requirements.txt`** — only in pipeline dependencies. No FAISS at backend runtime.
- `httpx==0.27.0` ✅ listed (used in `_push_latest_alerts`)
- Ollama client: uses `openai` library pointed at `http://localhost:11434/v1`, not a separate `ollama` package ✅

---

### A5. `fetchers/` — All Four Files

**Files in `fetchers/`:**
1. `ndma_scraper.py`
2. `official_alert_monitor.py`
3. `official_pdf_downloader.py` (not read — not requested in this audit)
4. `pdma_kp_fetcher.py`

#### `fetchers/ndma_scraper.py`

**What it does:** Scrapes `https://ndma.gov.pk/ndma-news/` with BeautifulSoup. Filters for flood/landslide keywords. Saves raw HTML to `data/raw/scraped/ndma_raw_{ts}.html` and parsed JSON to `data/raw/scraped/ndma_parsed_{ts}.json`.

**Does it parse into structured alert?** Partial — produces `{title, url, date_raw, source_org, scraped_at, requires_review:True}`. Not a full `AlertCreate` payload. No `body`, `hazard_type`, or `severity` fields.

**Is it invoked elsewhere?** ❌ No import found in any other file. Only runs if executed directly (`__main__`).

**Does it write to DB?** ❌ No. Writes to JSON files only. Explicitly states "Does NOT auto-insert into the knowledge base — human review required."

#### `fetchers/pdma_kp_fetcher.py`

**What it does:** Interactive CLI tool for **manual** ingestion of PDMA KP advisories. Prompts user for fields, validates, appends to `data/raw_advisories.json`.

**Is it invoked elsewhere?** ❌ No import found. Only runs if executed directly.

**Does it write to DB?** ❌ No. Writes to `data/raw_advisories.json` only. Comment: "No public PDMA KP API currently exists."

#### `fetchers/official_alert_monitor.py`

**What it does:** The only fetcher that actually POSTs to the backend DB.
- Scrapes 4 URLs (NDMA advisories, sitreps, guidelines; PDMA KP alerts-and-warnings)
- Downloads PDFs to `data/raw/alert_staging/`
- Extracts text with PyMuPDF
- Relevance filter: ≥2 matches from `RELEVANCE_KEYWORDS` (includes "chitral", "kp", flood, landslide, etc.)
- Classifies `hazard_type` and `severity` from keywords
- POSTs to `{BACKEND_URL}/alerts`

**Is it invoked elsewhere?** ✅ Yes — called as subprocess by `scheduler.py::_run_monitor_job()` (every 6 hours) and by `monitor.py::_run_fetcher()` (manual trigger).

**Payload field issue:** The alert dict POSTed to the backend does NOT include `source_url` or `verification_status` as top-level JSON fields. `source_url` is embedded only in the provenance prefix in `body`. `verification_status` defaults to `"DISCOVERED"` in the `AlertCreate` schema, not `"OFFICIAL-VERIFIED"` as the comment claims. ⚠️

---

### A6. Environment Variable Defaults — Code vs. Documented

| Variable | Code default (`config.py`) | `.env` file value | README documented |
|---|---|---|---|
| `SECRET_KEY` | `"disaster-dss-dev-secret-change-in-production"` | `"dev-secret-1153298759"` | "strong random value" in production |
| `ADMIN_API_KEY` | `"disaster-dss-dev-key-change-in-prod"` | `"disaster-dss-admin-dev-key"` | development default |
| `DATABASE_URL` | `sqlite+aiosqlite:///{TEMP}/disaster_dss_backend.sqlite` | Full path in TEMP | SQLite in TEMP folder ✅ matches |
| `CORS_ORIGINS` | `["http://localhost:8080","8081","3000","127.0.0.1:8080","127.0.0.1:3000"]` | `"http://localhost:8080,http://127.0.0.1:8080"` (different format) | Not documented |
| `ACCESS_TOKEN_TTL` | `3600` (seconds) | `ACCESS_TOKEN_EXPIRE_MINUTES=60` (different key name) | 1 hour |
| `LLM_PROVIDER` | `"none"` | `"ollama"` | ollama/llama3 |
| `LLM_MODEL` | `""` | `"llama3"` | llama3 |
| `LLM_BASE_URL` | `""` | `"http://localhost:11434/v1"` | localhost:11434 |
| `BACKEND_URL` | N/A (scheduler.py hardcodes `8002`) | `"http://127.0.0.1:8002"` | 8002 |

⚠️ `.env` sets `ADMIN_API_KEY=disaster-dss-admin-dev-key` but `config.py` sentinel is `"disaster-dss-dev-key-change-in-prod"`. These are **different strings**, so the `.env` value IS used (overrides the code default). Auth in `require_admin` will compare against the `.env` value.

---

## PART B — FLUTTER APP AUDIT

### B7. On-Device Query Flow (`retrieval/` and `rules_engine/`)

**File:** `app/lib/core/retrieval/retrieval_engine.dart`  
Both files carry: `// UNVERIFIED DRAFT — not run/tested against a real Flutter build.`

**`RomanUrduNormalizer._variants`** (8 entries):
```
'selab' → 'flood', 'sailaab' → 'flood', 'baarish' → 'rain',
'barish' → 'rain', 'paani' → 'water', 'pani' → 'water',
'zameen khisakna' → 'landslide', 'zamin khisakna' → 'landslide'
```
This is spelling-variant expansion only — 8 word mappings. It does NOT detect Urdu script. It cannot handle queries that don't match one of these exact strings.

**`RetrievalEngine.search()` SQL** (broken at runtime):
```sql
SELECT k.chunk_id, k.text, m.source_org, m.source_title, m.publication_date
FROM knowledge k
JOIN chunk_metadata m ON k.chunk_id = m.chunk_id
WHERE (k.text LIKE ? OR k.text LIKE ? ...)
LIMIT ?
```
**Critical bug:** The actual `knowledge.sqlite` has NO `knowledge` table, NO `chunk_metadata` table. The real table is `chunks` with `chunk_text` (not `text`), `source_org`, `doc_title` (not `source_title`), `pub_date` (not `publication_date`). This SQL will throw `OperationalError: no such table: knowledge` at runtime.

**`RulesEngine.buildResponse(query, chunks, {offline})`:**
- If `chunks.isEmpty` → returns "No verified official information found..." (EvidenceLevel.limited)
- Otherwise: `answerText = chunks.map((c) => c.text).join('\n\n')` — raw concatenation, no formatting
- EvidenceLevel: ≥3 chunks → high; 2 → moderate; 1 → limited

**Root cause of "repetitive chatbot answers" complaint:**  
The rules engine does not have any topic/phase detection. It literally concatenates raw chunk texts. Since the SQL is broken on mobile, the offline path always returns "No verified official information found." On web (`kIsWeb=true`), the app calls `_getOfflineFallback()` (Dart-side keyword matching), which does have topic detection. The repetition complaint is most likely from the web offline fallback returning the same answer before the `before/after/risk/GLOF` improvements were added.

---

### B8. `app/lib/core/localization/`

**File:** `app/lib/core/localization/language_service.dart`

- Language stored as `AppLanguage` enum: `english | urdu | romanUrdu`
- Persisted to `SharedPreferences` key `'app_language'`
- `isUrdu`, `isRomanUrdu` booleans used throughout app for UI text switching
- `isRtl` = `isUrdu` only (RTL for Urdu script)

**How language determines response language:**
1. In `chat_screen.dart` `_submitQuery()`: detected as `'ur'/'ru'/'en'` string, sent to backend via `POST /rag/query {language: lang}`.
2. In `rag_service.py` `_get_curated_answer(question, language)`: `ur` / `ru` values checked to return hardcoded Urdu/Roman Urdu answer strings.
3. In offline fallback (`_getOfflineFallback()` in `chat_screen.dart`): checks `LanguageService.instance.isUrdu` / `isRomanUrdu` and returns appropriate hardcoded strings.
4. SQLite retrieval (`/knowledge/search?language=`): filters `WHERE language = ?`. Since all 315 chunks are `language='en'`, Urdu queries return zero DB results (backed by `ground_truth_eval.json` which shows `relevant_chunk_ids: []` for all 6 Urdu queries).

---

### B9. `app/lib/features/chat/` — Chat Request/Response Flow

**File:** `app/lib/features/chat/chat_screen.dart`

**Does it call the backend?** ✅ Yes — always tries backend first.

**Request:**
```dart
POST /rag/query
{
  "question": queryText,
  "language": "en" | "ur" | "ru",  // from LanguageService
  "top_k": 5
}
```
Timeout: `Duration(seconds: 8)` (`api_service.dart`)

**Response handling:**
- If `apiResponse != null` AND `confidence != 'insufficient'` → online path:
  - Displays `answer` string from response
  - Formats `sources` as `"$org — $title\n$url"`
  - Shows `Tr.t('evidence_high')` label
- Else → offline path:
  - Mobile (`!kIsWeb`): `RetrievalEngine.search()` → `RulesEngine.buildResponse()` (broken SQL, see §B7)
  - Web (`kIsWeb`): `_getOfflineFallback(query)` — Dart-side keyword matching with hardcoded answers

**UI states that exist:**
- Loading: `_loading = true` shows `CircularProgressIndicator` in chat area via `_buildLoadingBubble()`
- Online indicator: green/gray dot + "Online"/"Offline" text in AppBar
- Empty state: greeting bubble + suggestion chips when `_messages.isEmpty`
- XAI expandable: "Why am I seeing this?" accordion per AI message with evidence level + sources

---

### B10. `app/lib/features/alerts/` — Alert Fetching and Display

**File:** `app/lib/features/alerts/official_alerts_screen.dart`  
**File:** `app/lib/core/services/alert_service.dart`

**How alerts are fetched:**
1. `AlertService.instance.start()` called in `initState`
2. Initial load: `GET /alerts?active_only=true&limit=50`
3. WebSocket: `ws://localhost:8002/ws/alerts` — pushes `{type:"new_alert", alert:{...}}` on new alert creation
4. HTTP polling fallback (when WebSocket disconnected): `GET /alerts?active_only=true&limit=20` every 30 seconds

**Parameters used:** `active_only=true` only. No `district`, `hazard_type`, or other filters sent from Flutter.

**Location used for filtering?** ❌ No. Alerts screen shows all active alerts with no location filter. The `district` field exists in the backend response and is displayed in the card UI, but is not used to filter what's shown.

**Local DB caching of alerts?** The offline package `knowledge.sqlite` (bundled asset) has an `alerts` table with 4 seed rows. The backend's `disaster_dss_backend.sqlite` has the live `alerts` table. There is **no separate local SQLite cache of live alerts** in the Flutter app — `AlertService.alerts` is an in-memory list only, lost on app restart.

**UI states:**
- Loading spinner (`_loading = true`) on initial fetch
- Empty state: icon + `Tr.t('no_alerts_filter')` + retry button
- New alert banner: `_NewAlertBanner` slides in from top, auto-dismisses after 5 seconds
- Connection badge: green dot "Real-time alerts active" (WebSocket live) or orange dot "Polling mode — updates every 30s"
- Pull-to-refresh: `RefreshIndicator` calls `AlertService.instance.refresh()`

---

### B11. `app/lib/core/local_db/` — Offline SQLite Tables

**File:** `app/lib/core/local_db/local_db.dart`  
File header: `// UNVERIFIED DRAFT — not run/tested against a real Flutter build.`

**Tables in `knowledge.sqlite` (offline_package asset):**
```sql
chunks (chunk_id PK, source_org, doc_title, pub_date, language,
        page_num, chunk_index, chunk_text, keywords, evidence_level, char_count)
alerts (alert_id PK, title, body, hazard_type, severity, issued_at, source_org, district)
package_meta (key PK, value)
```
Note: `source_url` column added later (directly via SQL `ALTER TABLE`) — not in `build_sqlite.py` schema definition.

**Tables in `hazard_grid.sqlite` (offline_package asset):**
```sql
hazard_grid (cell_id PK, lat, lon, elevation_m, slope_deg, river_dist_km,
             hazard_level, contributing_factors)
grid_meta (key PK, value)
```

**Migration mechanism?** ❌ None. The DB is copied once from asset bundle to device storage. No migration framework. Schema changes require rebuilding the asset and re-installing the app (or deleting the local copy so it gets re-copied).

---

### B12. Backend URL / Connectivity Determination

**File:** `app/lib/core/services/api_service.dart`

```dart
static String get baseUrl {
  if (kIsWeb) return 'http://localhost:8002';
  return 'http://10.0.2.2:8002';  // Android emulator loopback
}
```

**Is there an explicit "online" check?** ❌ No explicit connectivity pre-check. The `ApiService.get/post` simply attempts the HTTP call and returns `null` on `SocketException` or non-200 response.

**Could a slow/hanging request block the UI?** Partially. The 8-second timeout (`timeoutDuration`) prevents indefinite blocking. However, during those 8 seconds, `_loading = true` is set and the loading indicator is shown. The chatbot will spin for up to 8 seconds before showing the fallback. This is not a UI block — it's an intentional wait period.

**`connectivity_plus` package** is in `pubspec.yaml` and used in `AppStateProvider` to display an Online/Offline chip, but `ApiService` does not consult it before making requests.

---

## PART C — PIPELINE / OFFLINE PACKAGE AUDIT

### C13. Chunk Metadata Fields (extract.py / chunk.py)

**File:** `pipeline/rag/extract.py`

Output JSON shape per document:
```json
{
  "source_file": "...",
  "source_org": "...",
  "doc_title": "...",
  "pub_date": "...",
  "language": "en|ur",
  "pages": [{"page_num": N, "text": "..."}]
}
```

**File:** `pipeline/rag/chunk.py`

Each chunk dict (output to `data/chunks/*.json`):
```
chunk_id       — "{stem}_c{idx:04d}"
source_file    — original PDF filename
source_org     — from SOURCE_REGISTRY
doc_title      — from SOURCE_REGISTRY
pub_date       — extracted from PDF first 500 chars
language       — "en" or "ur" (detected by regex)
page_num       — which page the chunk came from
chunk_index    — sequential within document
chunk_text     — 60–600 char segment
keywords       — from KEYWORD_SEEDS matching
evidence_level — "official_national"/"official_provincial"/"official_meteorological"
char_count     — len(chunk_text)
```

**Metadata fields that DO exist:** source_org ✅, pub_date ✅, evidence_level ✅, language ✅, page_num ✅  
**Metadata fields that do NOT exist:** disaster_type (not attached per-chunk), phase (before/during/after — ❌ not a chunk field)  
**Aspirational in README but absent:** per-chunk `hazard_type` field and `phase` field are not part of the chunk schema.

---

### C14. `pipeline/package_builder/build_sqlite.py` — knowledge.sqlite Schema vs. Manifest

**Exact schema created by `build_sqlite.py`:**

`chunks` table (14 columns as listed in §B11 above). **No `source_url` column** in the CREATE TABLE statement.

`alerts` table: 8 columns (`alert_id`, `title`, `body`, `hazard_type`, `severity`, `issued_at`, `source_org`, `district`). No `verification_status`, `source_url`, `province`, `latitude`, `longitude`.

4 seed alerts hard-coded (seed_001 through seed_004).

**Manifest (`offline_package/manifest.json`) claims vs. code:**

| Claim | Verified |
|---|---|
| `version: "1.0.0"` | ✅ matches `PACKAGE_VERSION = "1.0.0"` in `build_sqlite.py` |
| `chunk_count: 315` | ✅ confirmed by actual SQLite query |
| `alert_count: 4` | ✅ 4 seed alerts in `build_sqlite.py` |
| `source_docs: 14` | ✅ 13 real PDFs + 1 synthetic demo = 14 |
| `lang_en: 315` | ✅ confirmed — all 315 chunks English |
| `lang_ur: 0` | ✅ confirmed — zero Urdu chunks |
| `lang_ru: 0` | ✅ confirmed |
| `knowledge_sqlite_size_kb: 216` | Not re-verified here; plausible for 315 chunks |

**Discrepancy:** `build_sqlite.py` does not add `source_url` to `chunks`, but `knowledge.py` queries `COALESCE(source_url, '') AS source_url`. This would cause `OperationalError: no such column: source_url` unless the column was added afterward via direct SQL `ALTER TABLE`. Based on earlier session work, the column was added manually — but this change is **not reflected in `build_sqlite.py`** so a fresh pipeline run would recreate the DB without `source_url`.

---

### C15. FAISS Embeddings — Are They Used at Runtime?

**File:** `pipeline/rag/embed.py`

- Generates `all_embeddings.npy` + `index.faiss` (FAISS `IndexFlatIP` with normalized vectors)
- Output path: `data/embeddings/`
- Comment: `"The embeddings are NOT shipped to the mobile app — the app uses keyword (LIKE) matching only."`

**Is FAISS loaded at runtime anywhere?**
- Searched all files in `backend/routers/`, `backend/services/`, `backend/core/`: ❌ No `import faiss` or `faiss.read_index()` found
- `requirements.txt`: `faiss-cpu` ❌ NOT listed
- **Verdict:** FAISS index is generated by the pipeline but **never loaded or queried at runtime**. All retrieval is keyword LIKE only.

---

## PART D — EVALUATION AUDIT

### D16. `evaluation/retrieval_eval.py` and `evaluation/ground_truth_eval.json`

**`retrieval_eval.py`:**
- Uses same SQL as `knowledge.py` backend (LIKE search)
- Roman Urdu fallback: if language="ru" returns 0 results, retries with language="en"
- Metrics: Precision@K, Recall@K, MRR, F1
- "Pass" criterion: at least one `relevant_chunk_id` appears in top-K results
- Stratifies by language AND hazard type in output
- `_annotation_note`: "AUTO-PREFILLED from K=5 retrieval. Review and correct relevant_chunk_ids before using for eval."
- Output: `evaluation/eval_summary.json`

**`ground_truth_eval.json` — Exact query type breakdown:**

| Language | Count | Notes |
|---|---|---|
| English (`"en"`) | 14 | All have relevant_chunk_ids populated |
| Urdu (`"ur"`) | 6 | ALL have `relevant_chunk_ids: []` — zero Urdu chunks in DB |
| Roman Urdu (`"ru"`) | 7 | Some have chunk IDs (via English fallback), some empty |
| **Total** | **27** | |

**Reconciliation vs. README claim of "14 English / 6 Urdu / 7 Roman Urdu":** ✅ Matches exactly.

**Honest limitation stated in eval code:** "Ground truth is self-constructed by the project team, not an external benchmark." All entries are `AUTO-PREFILLED` — they record what the system retrieved, not independently verified correct answers. Urdu `relevant_chunk_ids: []` means 0 relevant chunks were retrieved — the Urdu evaluation would show 0% precision/recall by design.

---

## PART E — RECONCILIATION

### E17 — README Claims vs. Actual Code

#### Claim: Working scheduled NDMA/PDMA scraper reaching the live alerts table

**Verdict: PARTIALLY — functional with a port bug**

Evidence:
- `backend/core/scheduler.py`: `AsyncIOScheduler` starts if `ENV != "test"` and `MONITOR_ENABLED != "0"` ✅
- `fetchers/official_alert_monitor.py`: scrapes 4 URLs, downloads PDFs, POSTs to backend `/alerts` ✅
- The scheduler correctly uses `BACKEND_URL=http://127.0.0.1:8002` ✅
- **BUG:** `backend/routers/monitor.py` manual trigger defaults to `http://127.0.0.1:8001` ❌
- `ndma_scraper.py` and `pdma_kp_fetcher.py` do NOT write to the database — they require human review or manual ingestion. Only `official_alert_monitor.py` writes to the DB.
- The fetcher does not set `source_url` or `verification_status` as top-level POST fields.

#### Claim: Working location filter on alerts

**Verdict: PARTIALLY — district string match only, no proximity search**

Evidence:
- `GET /alerts?district=Chitral` uses `AlertORM.district.ilike(f"%{district}%")` ✅
- Flutter `AlertService` does not pass any location filter — fetches all active alerts ❌
- No lat/lon radius filtering or link to `hazard_grid` coordinates ❌
- Alerts have `latitude`/`longitude` columns but no filtering logic uses them ❌

#### Claim: Working alert lifecycle (DISCOVERED/VERIFIED/PUBLISHED) enforced in code

**Verdict: YES — fully implemented on backend, not exposed in Flutter UI**

Evidence:
- `backend/routers/alerts.py` `_TRANSITIONS` dict enforces valid state progression ✅
- `POST /alerts/{id}/transition` writes state changes + `alert_history` row ✅
- `VALID_ALERT_STATES = {"DISCOVERED","FETCHED","VALIDATED","OFFICIAL-VERIFIED","PUBLISHED","EXPIRED"}` ✅
- Flutter `OfficialAlertsScreen` only uses `active_only=true`, does not display lifecycle states ❌

#### Claim: Working backend LLM (Ollama/Llama3) reachable from Flutter chat

**Verdict: PARTIALLY — code path exists, runtime dependency (Ollama) not installed**

Evidence:
- `rag_service.py::_call_ollama()` exists and is dispatched when `LLM_PROVIDER=="ollama"` ✅
- `.env` sets `LLM_PROVIDER=ollama, LLM_MODEL=llama3, LLM_BASE_URL=http://localhost:11434/v1` ✅
- Flutter chat calls `POST /rag/query` which reaches `query_rag()` ✅
- BUT: Step 1 (`_get_curated_answer()`) matches most queries and returns before LLM is ever called ⚠️
- If Step 1 misses and Step 2 passes, `_call_ollama()` attempts `http://localhost:11434/v1` — will fail with `ConnectionRefusedError` if Ollama not installed, returns `""`, falls to `_clean_chunks()` ❌
- **Actual answer quality at runtime without Ollama:** curated dictionary (Step 1) or raw sentence extraction (Step 4)

#### Claim: Working vector/semantic (FAISS) retrieval, or keyword-only everywhere

**Verdict: NO — keyword LIKE search everywhere at runtime**

Evidence:
- `backend/routers/knowledge.py::_do_search()`: LIKE search only ✅ (confirmed)
- `app/lib/core/retrieval/retrieval_engine.dart`: LIKE search (on wrong tables — broken)
- `pipeline/rag/embed.py`: generates FAISS index to `data/embeddings/index.faiss`
- `faiss-cpu` absent from `requirements.txt`; no `import faiss` anywhere in backend
- **Verdict: FAISS is pipeline-only artifact. Not used at query time.**

#### Claim: Default backend run port

**Verdict: 8002 in practice, 8001 in `main.py` docstring (outdated)**

Evidence:
- `backend/main.py` docstring: `--port 8001` ❌ (outdated)
- `backend/.env`: `BACKEND_URL=http://127.0.0.1:8002` ✅
- `backend/core/scheduler.py`: default `http://127.0.0.1:8002` ✅
- `app/lib/core/services/alert_service.dart`: `ws://localhost:8002` ✅
- `app/lib/core/services/api_service.dart`: `http://localhost:8002` ✅
- `backend/routers/monitor.py`: default `http://127.0.0.1:8001` ❌ (live bug)

---

### E18 — Plain Verdict

**Real-time alerts and RAG chatbot: scaffolded/partially implemented and need substantial completion.**

More specifically:

**Real-time alerts** are closer to "implemented and need refinement":
- The scheduled monitor, WebSocket broadcast, and Flutter receiver are all present and functionally connected
- The gaps are specific and fixable: the monitor.py port bug, missing `source_url` in POST payload, and no location-based filtering in Flutter

**RAG chatbot** is closer to "scaffolded and needs substantial completion":
- The `/rag/query` endpoint exists and is called correctly
- But the answer source at runtime is a hardcoded Python dictionary (`_get_curated_answer`), not actual retrieval from the 315 document chunks
- The actual chunk retrieval path (SQL LIKE → LLM generation) is only reached for queries that don't match a curated keyword — and even then, LLM generation is non-functional without Ollama
- The mobile offline retrieval path (`retrieval_engine.dart`) has a critical SQL bug that must be fixed before it can work at all
- All 315 knowledge chunks are English; multilingual retrieval returns 0 results for Urdu/Roman Urdu

**Three specific items still entirely aspirational:**
1. Per-chunk `disaster_type` and `phase` (before/during/after) metadata — not present in the schema
2. FAISS/semantic retrieval at query time — pipeline artifact only
3. Urdu/Roman Urdu knowledge chunks — manifest confirms `lang_ur=0, lang_ru=0`

---

*This document was generated by read-only code inspection on 2026-09-14. No files were modified.*
