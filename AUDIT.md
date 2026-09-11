# Disaster DSS — Repository Audit

**Audit date:** September 2026
**Method:** Direct inspection of every relevant file — not README claims.
**Auditor note:** README and TEAM_REQUIREMENTS.md make several claims that do not
match the current codebase. All discrepancies are noted below with exact file paths
and line references.

Legend: ✅ Fully implemented | ⚠️ Partial / mock | ❌ Missing | 🔴 Insecure

---

## 1. AUTHENTICATION

### (a) Fully implemented and working

| What | File | Lines |
|------|------|-------|
| bcrypt password hashing (12 rounds, direct bcrypt library) | `backend/core/security.py` | 28–40 |
| Timing-safe login via pre-computed dummy hash | `backend/core/security.py` | 31–35 |
| JWT access tokens (HS256, python-jose) with `sub`, `email`, `role`, `exp`, `jti` | `backend/core/security.py` | 51–66 |
| Opaque refresh tokens — stored as SHA-256 hash, never plaintext | `backend/core/security.py` | 74–76 |
| Refresh token rotation — old token revoked on every refresh | `backend/routers/auth.py` | 106–112 |
| Refresh token revocation table (`RefreshTokenORM`) | `backend/models/db_models.py` | 52–66 |
| `POST /auth/register` — duplicate email → HTTP 409 | `backend/routers/auth.py` | 50–66 |
| `POST /auth/login` — wrong password → HTTP 401, deactivated → 403 | `backend/routers/auth.py` | 69–100 |
| `POST /auth/refresh` — rotates token, checks expiry, checks revocation | `backend/routers/auth.py` | 103–138 |
| `POST /auth/logout` — revokes refresh token, always 204 | `backend/routers/auth.py` | 141–152 |
| `GET /auth/me` — requires valid JWT | `backend/routers/auth.py` | 155–157 |
| `get_current_user` dependency wired correctly | `backend/core/security.py` | 82–108 |
| `get_current_admin` role check | `backend/core/security.py` | 111–115 |
| `UserORM.role` field (user/admin) | `backend/models/db_models.py` | 33 |
| Password minimum 8 characters enforced in Pydantic | `backend/models/db_models.py` | 138 |
| Production fail-fast if default secrets used (ENV=production) | `backend/core/config.py` | 68–83 |
| Flutter: `flutter_secure_storage` added to pubspec for mobile token storage | `app/pubspec.yaml` | (flutter_secure_storage dep) |
| Flutter: `auth_service.dart` uses `_readSecure`/`_writeSecure` with platform branch | `app/lib/core/services/auth_service.dart` | 37–58 |
| Flutter: `isSessionValid()` checks token age against stored issue time | `app/lib/core/services/auth_service.dart` | 175–183 |
| 20/20 pytest tests covering all auth scenarios | `backend/tests/test_auth.py` | all |

### (b) Partial / mocked

| What | File | Issue |
|------|------|-------|
| Rate limiting removed from auth endpoints | `backend/routers/auth.py` | `@limiter.limit` decorators were removed to fix test compatibility. No rate limiting currently active on login/register. |
| Web token storage uses `SharedPreferences` | `app/lib/core/services/auth_service.dart` | 41–58 — acceptable for prototype but `SharedPreferences` is not secure storage on web. HttpOnly cookies would be production-correct. |
| Token refresh on Flutter: `refreshAccessToken()` exists | `app/lib/core/services/auth_service.dart` | 101–116 — implemented but no automatic retry on 401 in `AlertsScreen` or `ChatScreen`. Manual re-login required after token expiry in those screens. |

### (c) Missing

| What | Notes |
|------|-------|
| Rate limiting on `/auth/login` and `/auth/register` | Was removed; no brute-force protection currently active. |
| Email verification | No email verification flow exists. |
| Password reset flow | No forgot-password or reset endpoint. |
| Admin user seeding | No way to create the first admin account without directly editing the DB. |

### (d) Insecure

| What | File | Line | Risk |
|------|------|------|------|
| Default `ADMIN_API_KEY` hardcoded in `alerts.py` | `backend/routers/alerts.py` | 32 | Falls back to `"disaster-dss-dev-key-change-in-prod"` if env var not set in development. **Only safe in production** because `config.py` fails startup when `ENV=production`. In development mode the default key is active. |
| Default `ADMIN_API_KEY` duplicated in `sync.py` | `backend/routers/sync.py` | 22 | Same issue — reads directly from `os.getenv` rather than from the central `settings` singleton. Two sources of truth for the same value. |
| `SECRET_KEY` defaults to dev value in development | `backend/core/config.py` | 40 | Intentional for dev convenience, but tokens signed with the dev key would be valid across all dev instances. |

---

## 2. DATABASE SCHEMA

### (a) Fully implemented

| Table | File | What it stores |
|-------|------|----------------|
| `users` | `backend/models/db_models.py` L27–44 | id, name, email, hashed_password, role, district, language, is_active, created_at, updated_at |
| `refresh_tokens` | `backend/models/db_models.py` L50–66 | SHA-256 token hash, user_id, expires_at, revoked, revoked_at, user_agent, ip_address |
| `alerts` | `backend/models/db_models.py` L70–107 | Full provenance: source_org, source_url, fetch_timestamp, content_hash, verification_status, district, province, lifecycle state |
| `package_updates` | `backend/models/db_models.py` L110–120 | version, built_at, chunk_count, checksums |
| Indexes on alerts | `backend/models/db_models.py` L103–107 | district, hazard_type, issued_at, verification_status |

**Hard constraint 4 (provenance) is satisfied in schema**: `source_org`, `source_url`,
`fetch_timestamp`, `content_hash`, `verification_status` all exist in `AlertORM`.

### (b) Partial

| What | File | Issue |
|------|------|-------|
| Alert `create_alert` endpoint does NOT populate `source_url`, `fetch_timestamp`, or `content_hash` | `backend/routers/alerts.py` L73–87 | The schema has the columns but `create_alert` does not map them from the payload — they are left NULL even when the payload includes them. `AlertCreate` Pydantic schema does have `source_url` (L167) but `create_alert` ignores it. |
| `verification_status` not set during creation | `backend/routers/alerts.py` L73–87 | Hardcoded to `AlertORM` default (`"DISCOVERED"`) regardless of `payload.verification_status`. |
| No `alert_history` table | — | Alert updates (`PUT /alerts`) overwrite in-place with no history. README mentions alert history but no history table exists. |
| No Alembic migrations | — | Schema changes require deleting the SQLite file. `init_db()` uses `create_all` which skips existing tables. |

### (c) Missing

| What | Notes |
|------|-------|
| `sources` table | No dedicated table tracking official data sources. |
| `ingestion_runs` table | No audit log of when ingestion ran, what was fetched. |
| `documents` table | No table linking chunks to their source document with URL, pub date, checksum. |
| `chunks_meta` table | Chunks are only in the offline SQLite (`knowledge.sqlite`), not mirrored in the backend DB. |
| Foreign key `refresh_tokens.user_id → users.id` | `backend/models/db_models.py` L57 — field exists but no SQLAlchemy `ForeignKey()` constraint defined. |

### (d) Insecure

| What | File | Line | Risk |
|------|------|------|------|
| No FK constraint on `refresh_tokens.user_id` | `backend/models/db_models.py` | 57 | A refresh token row could reference a deleted user. Low risk in SQLite but would be an integrity issue in PostgreSQL. |

---

## 3. RAG / RETRIEVAL

### (a) Fully implemented

| What | File | Lines |
|------|------|-------|
| Offline keyword LIKE retrieval (SQLite, no internet) | `app/lib/core/retrieval/keyword_retriever.dart` | all |
| Roman Urdu spelling-variant expansion (30+ groups) | `app/lib/core/retrieval/roman_urdu_normalizer.dart` | all |
| Auto-detection of Roman Urdu from query content | `app/lib/core/retrieval/keyword_retriever.dart` | 60–62 |
| English fallback when Roman Urdu returns no results | `app/lib/core/retrieval/keyword_retriever.dart` | 74–80 |
| Score expression (hit-count ranking) | `app/lib/core/local_db/database_helper.dart` | 95–107 |
| Source provenance on every result (source_org, doc_title, pub_date, evidence_level) | `app/lib/core/retrieval/keyword_retriever.dart` | 7–19 |
| kIsWeb guard — retrieval silently skips on web (returns empty), no crash | `app/lib/core/local_db/database_helper.dart` | 39–40 |
| 315 real NDMA/PDMA chunks in `knowledge.sqlite` | `app/assets/offline_package/knowledge.sqlite` | — |
| FAISS index built by pipeline (384-dim, multilingual MiniLM) | `data/embeddings/index.faiss` | — |
| Backend `/knowledge/search` uses async thread-pool executor (non-blocking) | `backend/routers/knowledge.py` | 43–46 |
| P@5 = 1.000, R@5 = 1.000 on 20 annotated queries | `evaluation/eval_summary.json` | — |

### (b) Partial

| What | File | Issue |
|------|------|-------|
| FAISS semantic search built but NOT wired into runtime | `data/embeddings/index.faiss` exists, `pipeline/rag/embed.py` builds it | The backend `/knowledge/search` endpoint uses only SQLite LIKE matching, identical to the Flutter offline path. FAISS is never loaded or queried at runtime. The docstring says "keyword + FAISS semantic search" but FAISS is not called. |
| Backend `/knowledge/search` identical to offline Flutter retrieval | `backend/routers/knowledge.py` L58–82 | No reranking, no semantic enrichment. Online search provides no advantage over offline. |
| 0 Urdu chunks in knowledge.sqlite | — | All 315 chunks are English. Urdu queries get 0 results with no fallback to English in the backend endpoint. The Flutter `KeywordRetriever` has an English fallback only for Roman Urdu, not for Urdu. |

### (c) Missing

| What | Notes |
|------|-------|
| Semantic FAISS search at runtime | Index exists, not wired. `pipeline/rag/embed.py` never called from any endpoint. |
| LLM/RAG generation layer | No LLM integration exists anywhere. Hard constraint 5 (refuse on low confidence) and constraint 6 (swappable provider) have no implementation to apply to. |
| Confidence score exposed to UI | `RetrievalResult.score` (int hit-count) is available but not shown in `ChatScreen` as a visible confidence indicator. |
| Urdu → English fallback in retrieval | `KeywordRetriever` only falls back for Roman Urdu, not for Urdu. |

---

## 4. GIS / HAZARD GRID

### (a) Fully implemented

| What | File | Lines |
|------|------|-------|
| Deterministic hazard classifier (slope + river distance thresholds) | `app/lib/core/rules_engine/hazard_rules.dart` | all |
| Correct thresholds: slope HIGH>30°, MED>15°; river HIGH<0.5km, MED<1.5km | `app/lib/core/rules_engine/hazard_rules.dart` | 10–13 |
| Worst-case combination (conservative for life-safety) | `app/lib/core/rules_engine/hazard_rules.dart` | 66–74 |
| Always-visible disclaimer constant | `app/lib/core/rules_engine/hazard_rules.dart` | 109–113 |
| GPS permission request with denied/permanently-denied handling | `app/lib/features/map/hazard_map_screen.dart` | 39–56 |
| `.timeout()` on `Geolocator.getCurrentPosition` (v12 compatible) | `app/lib/features/map/hazard_map_screen.dart` | 58–62 |
| Out-of-study-area state handled | `app/lib/features/map/hazard_map_screen.dart` | 64–70 |
| 10,000 cells at 0.01° covering Chitral (lat 35.5–36.5, lon 71.5–72.5) | `offline_package/hazard_grid.sqlite` | — |
| GIS computation pipeline preserved | `pipeline/gis/compute_hazard_grid.py` | all |
| Synthetic terrain model clearly documented (Chitral-calibrated, not validated) | `pipeline/gis/compute_hazard_grid.py` | 44–48 |
| Python pipeline thresholds match Dart thresholds exactly | `pipeline/gis/compute_hazard_grid.py` L58–60 matches `hazard_rules.dart` L10–13 | — |

### (b) Partial

| What | File | Issue |
|------|------|-------|
| No actual map widget | `app/lib/features/map/hazard_map_screen.dart` | Screen is named "Hazard Map" but shows only a card with GPS coordinates and a text hazard level. No `flutter_map`, `google_maps_flutter`, or similar. User cannot see a visual map. |
| `contributing_factors` stored as JSON string in SQLite | `pipeline/gis/compute_hazard_grid.py` L145 | Stored as `json.dumps(factors)` — the Dart side does not parse this JSON; `HazardMapScreen` does not display contributing factors from the grid row, only from the Dart-side classifier re-run. |

### (c) Missing

| What | Notes |
|------|-------|
| Visual map rendering | No map tile library integrated. |
| Alert-to-location linking | No endpoint or query to answer "what active alerts affect my current coordinates?" |
| GLOF indicator | Explicitly out of scope but listed in README future work. |

---

## 5. INGESTION (fetchers/)

### (a) Fully implemented

| What | File | Lines |
|------|------|-------|
| Real official PDF downloader with checksums, size validation, manifest | `fetchers/official_pdf_downloader.py` | all |
| 10 real NDMA PDFs downloaded from verified ndma.gov.pk URLs | `data/raw/download_manifest.json` | — |
| Official URL monitor: HTML scrape → change detection → PDF download → text extract | `fetchers/official_alert_monitor.py` | all |
| State persistence (seen URLs) prevents re-processing | `fetchers/official_alert_monitor.py` | 87–96 |
| Provenance prepended to alert body (source_org, URL, fetch time, status) | `fetchers/official_alert_monitor.py` | 162–167 |
| Relevance filter before ingestion (Chitral/KP keywords) | `fetchers/official_alert_monitor.py` | 115–119 |
| Dry-run mode (`--dry-run`) for safe testing | `fetchers/official_alert_monitor.py` | 169, 190 |
| No fabricated REST API — only HTML page scraping | `fetchers/official_alert_monitor.py` | 71–93 |
| Manual advisory ingestor with validation | `fetchers/pdma_kp_fetcher.py` | all |

### (b) Partial

| What | File | Issue |
|------|------|-------|
| `source_url` not passed to backend `AlertCreate` payload | `fetchers/official_alert_monitor.py` | L153–167 — `alert` dict has `source_org` but not `source_url` key. URL appears only in body text prefix, not in the dedicated database column. |
| `fetch_timestamp` not passed as ISO field | `fetchers/official_alert_monitor.py` | L155 — `issued_at` is set to `run_ts` (fetch time used as issued_at). No separate `fetch_timestamp` field passed to backend. |
| `content_hash` not computed or passed | `fetchers/official_alert_monitor.py` | Missing entirely. AlertORM has the column but ingestion never sets it. |
| `verification_status` only in body text, not as field | `fetchers/official_alert_monitor.py` | L163 — `"STATUS: official-verified"` is prepended to body text but `verification_status` is not passed as a payload field. The AlertCreate schema has it but the dict does not include it. |
| Monitor not scheduled | — | Must be run manually. No cron, no APScheduler, no background task in the FastAPI backend. |
| `BACKEND_URL` hardcoded fallback to port 8001 | `fetchers/official_alert_monitor.py` | L37 | Backend now runs on 8002 in current dev setup. |

### (c) Missing

| What | Notes |
|------|-------|
| Scheduled ingestion | No automatic periodic execution. |
| Deduplication by content hash | `content_hash` never computed; duplicate detection not implemented. |
| Changed-document detection | State file tracks seen URLs but not content changes to already-seen documents. |
| Alert expiry / lifecycle transitions | `verification_status` field exists in DB but no code transitions it (DISCOVERED → FETCHED → VALIDATED → PUBLISHED). |

---

## 6. ONLINE / OFFLINE SYNC

### (a) Fully implemented

| What | File | Lines |
|------|------|-------|
| `AppStateProvider` monitors connectivity in real time | `app/lib/core/providers/app_state_provider.dart` | all |
| Alerts sync from backend when online | `app/lib/features/alerts/alerts_screen.dart` | 50–82 |
| Alerts cached in local SQLite for offline use | `app/lib/core/local_db/database_helper.dart` | 130–141 |
| Alerts JSON response correctly parsed (`decoded['alerts']` as List) | `app/lib/features/alerts/alerts_screen.dart` | 65 |
| Backend URL from `AppConfig` (no hardcoding) | `app/lib/core/config/app_config.dart` | all |
| `--dart-define=BACKEND_URL` override supported | `app/lib/core/config/app_config.dart` | 17–19 |
| DB version check on startup — re-copies bundled asset if version bumped | `app/lib/core/local_db/database_helper.dart` | 35–44 |
| `_ensureAlertsTable()` creates alerts table if missing | `app/lib/core/local_db/database_helper.dart` | 47–64 |
| `kIsWeb` guards on all SQLite calls | `app/lib/core/local_db/database_helper.dart` | 39, 91, 126, 135, 149, 165 |

### (b) Partial

| What | File | Issue |
|------|------|-------|
| Sync is full replace, not incremental | `app/lib/features/alerts/alerts_screen.dart` | 66–74 — `upsertAlert()` replaces all alerts on each sync. No version/timestamp-based incremental sync. |
| No checksum verification before DB update | `app/lib/core/local_db/database_helper.dart` | `_openDb` checks only `stored_version < bundledDbVersion`. No SHA-256 checksum of the asset file verified. |
| No atomic replace (temp file → verify → rename) | `app/lib/core/local_db/database_helper.dart` | 50–56 — `File(destPath).writeAsBytes(bytes)` writes directly. Interrupted write could corrupt the DB. |
| `package_meta` table not populated by `_ensureAlertsTable` | `app/lib/core/local_db/database_helper.dart` | 58–63 — table created if missing but never populated with actual metadata during runtime sync. |

### (c) Missing

| What | Notes |
|------|-------|
| Incremental sync by timestamp/version | Every sync fetches all active alerts from backend. |
| Pull-to-refresh with last-synced timestamp | `AlertsScreen` has pull-to-refresh but it re-fetches everything. |
| Retry with exponential backoff | Sync failure shows snackbar and stops. No retry logic. |
| Background sync when connectivity restored | `AppStateProvider` detects connectivity change but does not trigger sync automatically. |
| Offline knowledge package download | `/sync/publish` and `/sync/status` endpoints exist but Flutter never uses them to download an updated `knowledge.sqlite`. |

---

## 7. TESTING

### (a) Fully implemented

| What | File | Count |
|------|------|-------|
| Backend auth pytest suite | `backend/tests/test_auth.py` | 20 tests, all passing |
| Covers: register, duplicate, password min, login, wrong-pw, case-insensitive, token, refresh, rotation, revocation, logout, admin rejection, health | — | — |
| In-memory SQLite per test (full isolation) | `backend/tests/conftest.py` | all |
| Rate limiter bypassed cleanly (removed from decorators) | `backend/routers/auth.py` | — |
| Retrieval evaluation (P@5, R@5, MRR, F1 per language + hazard) | `evaluation/retrieval_eval.py` | 20 annotated queries |
| P@5 = R@5 = MRR = F1 = 1.000 for EN and RU | `evaluation/eval_summary.json` | — |

### (b) Partial

| What | File | Issue |
|------|------|-------|
| Flutter test file is a placeholder | `app/test/widget_test.dart` | Contains only `expect(true, isTrue)` — not a real test. |
| No alerts API tests | — | No pytest tests for `POST /alerts`, `GET /alerts`, `PUT /alerts`, `DELETE /alerts`. |
| No knowledge API tests | — | No pytest tests for `/knowledge/search`, `/knowledge/meta`. |
| No sync API tests | — | No pytest tests for `/sync/status`, `/sync/publish`. |
| No integration test (register → login → sync → offline → verify) | — | The end-to-end scenario from the spec does not exist as an automated test. |
| Urdu queries skipped in evaluation | `evaluation/eval_summary.json` | 6 Urdu GT queries have `relevant_chunk_ids: []` — auto-generated from retrieval but 0 Urdu chunks exist so all are empty. |

### (c) Missing

| What | Notes |
|------|-------|
| Flutter widget tests (onboarding, login, dashboard, chat, map) | None exist. |
| Flutter service tests (`auth_service.dart`, `database_helper.dart`) | None exist. |
| Backend tests for alerts, knowledge, sync, monitor routers | None exist. |
| Offline regression test (run with network disabled) | No automated verification that offline path still works. |
| `go_bag_screen.dart` test | None — screen added from branch with no tests. |

### (d) Insecure

| What | File | Risk |
|------|------|------|
| `go_bag_screen.dart` is in OneDrive placeholder state (`-a---l`) | `app/lib/features/go_bag/go_bag_screen.dart` | Flutter analyzer cannot read it — `flutter analyze` currently reports 2 errors (uri_does_not_exist, creation_with_non_type). The app will not compile with `go_bag` tab enabled. |

---

## 8. HARD CONSTRAINT COMPLIANCE SUMMARY

| Constraint | Status | Evidence |
|-----------|--------|---------|
| 1. Offline path never broken | ✅ | `kIsWeb` guards on all SQLite calls; hazard_grid + knowledge.sqlite bundled; evaluated P@5=1.0 |
| 2. Never invent NDMA/PDMA/PMD API | ✅ | Fetcher uses HTML scraping + PDF download only; no REST client to official org |
| 3. No hardcoded production secrets | ⚠️ | `config.py` fails startup in production. Dev defaults still active in development. `ADMIN_API_KEY` duplicated in `alerts.py:32` and `sync.py:22` — should read from `settings` singleton. |
| 4. Every alert carries source/URL/timestamp/status | ⚠️ | Schema correct. `create_alert` endpoint does not map `source_url`, `fetch_timestamp`, `content_hash`, or `verification_status` from payload into DB columns. Fetcher embeds URL in body text but not in the dedicated column. |
| 5. LLM refuses on low confidence | N/A | No LLM layer exists. Constraint applies when LLM is added. |
| 6. LLM provider swappable via config | N/A | No LLM layer exists. |
| 7. Run all 4 checks before marking done | ⚠️ | `pytest`: 20/20 ✅. `retrieval_eval.py`: P@5=1.0 ✅. `flutter analyze`: 2 errors ❌ (go_bag OneDrive issue). `flutter test`: placeholder only ⚠️. |

---

## 9. ITEMS REQUIRING IMMEDIATE ACTION (before any new feature work)

Priority ordered:

1. **`go_bag_screen.dart` OneDrive lock** — `flutter analyze` shows 2 errors.
   Fix: re-write file content from a non-OneDrive terminal, or move project outside OneDrive sync.

2. **`create_alert` does not persist `source_url`, `fetch_timestamp`, `content_hash`, `verification_status`** — Hard constraint 4 violated at the API layer even though the schema is correct.
   Fix: `backend/routers/alerts.py` L73–87 — set these fields from `payload`.

3. **Fetcher does not pass `source_url` as structured field** — URL only in body text prefix.
   Fix: `fetchers/official_alert_monitor.py` L153–167 — add `"source_url": url` to the alert dict.

4. **`ADMIN_API_KEY` read from `os.getenv` directly in `alerts.py` and `sync.py`** — not from `settings` singleton.
   Fix: import `settings` from `backend.core.config` in both routers.

5. **Rate limiting removed** — no brute-force protection on login.
   Fix: re-implement as middleware or use `slowapi` correctly in tests.

6. **No foreign key constraint on `refresh_tokens.user_id`** — `backend/models/db_models.py` L57.
   Fix: add `ForeignKey("users.id", ondelete="CASCADE")`.

7. **Flutter widget tests are placeholder** — `app/test/widget_test.dart` line 6.
   Fix: implement at minimum offline retrieval and auth service unit tests.

---

*Audit generated from direct code inspection. No files were modified.*
