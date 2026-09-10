# Disaster DSS — Team Requirements

**Project:** Offline-first disaster decision-support system for Chitral, KP  
**Repo:** https://github.com/duaiqbal/Climate-Disaster  
**Architecture:** Flutter Web/Mobile app + FastAPI backend + SQLite databases

> Read this before touching any code. Everything here is based on the actual
> existing codebase — nothing is invented or assumed.

---

## How the Two Roles Connect

```
Flutter App  (Frontend Developer owns this)
   │
   ├── Offline path  ──►  SQLite on device (knowledge.sqlite + hazard_grid.sqlite)
   │
   └── Online path   ──►  HTTP ──► FastAPI Backend  (Backend Developer owns this)
                                       ├── POST /auth/register
                                       ├── POST /auth/login
                                       ├── GET  /alerts
                                       ├── GET  /knowledge/search
                                       └── GET  /health
```

**The contract between both roles is the API response shape.**
If the backend renames a JSON field, the Flutter app crashes. Always coordinate
before changing any API schema.

---

---

# ROLE 1 — Backend Developer

---

## Technologies and Versions

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10 or higher (3.14 on this machine) | Language runtime |
| FastAPI | 0.111.0 | Web API framework |
| Uvicorn | 0.29.0 | ASGI server |
| SQLAlchemy | 2.0.30 | Async ORM |
| aiosqlite | 0.20.0 | Async SQLite driver (required — do not remove) |
| Pydantic | 2.7.1 | Request/response validation and serialisation |
| python-multipart | 0.0.9 | Form data handling |
| httpx | 0.27.0 | HTTP client used in tests |
| pytest | 8.2.2 | Test runner |
| pytest-asyncio | 0.23.7 | Async test support |

## Required Technical Knowledge

- Python async/await — `async def`, `await`, `asynccontextmanager`
- FastAPI routing, dependency injection (`Depends(get_db)`)
- Pydantic v2 models: `model_validate()`, `@field_validator`, `model_config`
- SQLAlchemy async sessions: `AsyncSession`, `await session.execute()`, `await session.commit()`
- HTTP status codes: 200, 201, 401, 403, 409, 503
- Basic password security: PBKDF2-HMAC-SHA256, HMAC token signing
- SQLite basics: queries, schema, no migration tool needed for this project

## Setup (Run Once)

```powershell
# Step 1 — Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Step 2 — Install dependencies
pip install -r backend/requirements.txt

# Step 3 — Verify imports work
python -c "from backend.routers import alerts, auth, knowledge, sync; print('All imports OK')"
```

## Start the Backend

```powershell
# ALWAYS run from project root — NOT from inside the backend/ folder
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

- API browser docs: http://127.0.0.1:8001/docs
- Health check: http://127.0.0.1:8001/health

**Why port 8001?** Port 8000 may already be occupied. Always use 8001 locally.

## Validate Your Work

```powershell
# Run from project root with backend already started on port 8001
python validate_backend.py
# Expected output: 14 passed | 0 failed
```

## Your Files

| File | What it does |
|------|-------------|
| `backend/main.py` | App factory, startup lifecycle, CORS, router registration |
| `backend/database.py` | Async SQLAlchemy engine and session factory |
| `backend/models/db_models.py` | ORM table models + all Pydantic schemas |
| `backend/routers/auth.py` | Register and login endpoints |
| `backend/routers/alerts.py` | Disaster alert CRUD (list, create, update, delete) |
| `backend/routers/knowledge.py` | Read-only search over knowledge.sqlite |
| `backend/routers/sync.py` | Offline package version management |
| `backend/requirements.txt` | All pinned Python dependencies |
| `validate_backend.py` | Live automated test script (run to verify everything works) |

## API Endpoints You Own

| Method | Endpoint | Auth needed | Notes |
|--------|----------|-------------|-------|
| GET | `/health` | None | Returns `{"status":"ok","version":"1.0.0","db":"sqlite"}` |
| POST | `/auth/register` | None | HTTP 201 on success, HTTP 409 on duplicate email |
| POST | `/auth/login` | None | HTTP 200 with token, HTTP 401 on wrong credentials |
| GET | `/alerts` | None | Returns `{"total": N, "alerts": [...]}` |
| POST | `/alerts` | Admin key | Create new alert |
| PUT | `/alerts/{id}` | Admin key | Update alert |
| DELETE | `/alerts/{id}` | Admin key | Soft-delete (sets is_active=false) |
| GET | `/knowledge/search` | None | `?q=flood&language=en&limit=10` |
| GET | `/knowledge/chunks` | None | Paginated chunk list |
| GET | `/knowledge/meta` | None | Offline package metadata |
| GET | `/sync/status` | None | Latest package version info |

## Critical Response Shapes — Never Break These

The Flutter app depends on these **exact field names and structures**.

**POST /auth/login — TokenResponse:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "Tooba Iqbal",
    "email": "tooba@example.com",
    "district": null,
    "language": "en",
    "is_active": true,
    "created_at": "2024-08-01T10:00:00"
  }
}
```

**GET /alerts — AlertListResponse:**
```json
{
  "total": 3,
  "alerts": [
    {
      "alert_id": "abc123",
      "title": "Flood Warning Chitral",
      "body": "Advisory text...",
      "hazard_type": "flood",
      "severity": "HIGH",
      "issued_at": "2024-08-01T06:00:00",
      "source_org": "NDMA",
      "district": "Chitral",
      "language": "en",
      "is_active": true,
      "created_at": "2024-08-01T00:00:00"
    }
  ]
}
```

The Flutter alerts screen does `decoded['alerts'] as List`. If you rename that
key or wrap it differently, the app will crash on sync.

## How Authentication Works

- Passwords hashed with `PBKDF2-HMAC-SHA256` at 200,000 iterations (never stored plaintext)
- Tokens are custom `base64(payload) + "." + hmac_sha256(payload)` — 24 hour TTL
- Admin-only write endpoints check `X-Admin-Key` header
- All logic is in `backend/routers/auth.py` — do not move it

## Environment Variables

| Variable | Development default | Must change for production? |
|----------|--------------------|-----------------------------|
| `SECRET_KEY` | `disaster-dss-dev-secret-change-in-production` | YES |
| `ADMIN_API_KEY` | `disaster-dss-dev-key-change-in-prod` | YES |
| `DATABASE_URL` | `sqlite+aiosqlite:///backend/disaster_dss_backend.sqlite` | Optional (use PostgreSQL) |
| `KNOWLEDGE_DB` | Auto-detected (tries project root then Flutter assets) | Only if you move the file |
| `CORS_ORIGINS` | `*` | Set to your domain in production |
| `SQL_ECHO` | (empty) | Set to `1` to log all SQL queries while developing |

## What You Can Safely Change

- Add new endpoints to any router file
- Add new columns to ORM models (never remove existing columns)
- Improve error messages and HTTP status codes
- Add logging statements
- Add new Pydantic validators
- Expand filter options on `/alerts`

## What You Must Not Break

- `POST /auth/login` must always return `access_token` + `user` object
- `GET /alerts` must always return `{"total": N, "alerts": [...]}`
- `POST /auth/register` must return HTTP 201, and HTTP 409 for duplicate email
- `POST /auth/login` must return HTTP 401 for wrong credentials
- Never rename existing JSON response field names
- Never disable CORS — Flutter Web will fail immediately
- Never run uvicorn from inside the `backend/` folder (imports will break)
- Never store plaintext passwords or log token values

## Handing Off to Frontend Developer

- Tell the frontend developer the exact new field name and HTTP status code before
  changing any API response
- Test with `validate_backend.py` before every commit
- Use this command to add only your backend files to git:

```powershell
git add backend/ validate_backend.py
git commit -m "backend: describe your change here"
git push origin master
```

---

---

# ROLE 2 — Frontend Developer

---

## Technologies and Versions

| Tool | Version | Purpose |
|------|---------|---------|
| Flutter SDK | 3.47.2 | Cross-platform UI framework |
| Dart | bundled with Flutter | Language |
| sqflite | ^2.3.3 | SQLite on Android/iOS (not used on web) |
| path_provider | ^2.1.3 | Device file paths (Android/iOS only) |
| provider | ^6.1.2 | State management |
| geolocator | ^12.0.0 | GPS location |
| http | ^1.2.1 | HTTP calls to backend |
| shared_preferences | ^2.3.1 | Local key-value storage (auth token, language, settings) |
| connectivity_plus | ^6.0.3 | Online/offline detection |
| permission_handler | ^11.3.1 | Runtime permissions (location) |
| intl | ^0.20.3 | Date/number formatting |

## Required Technical Knowledge

- Flutter widgets: `StatelessWidget`, `StatefulWidget`, `setState()`
- Provider state management: `ChangeNotifier`, `context.watch<>()`, `context.read<>()`
- SQLite queries via `sqflite` (Android/iOS only — guarded with `kIsWeb` on web)
- HTTP with the `http` package: `http.post()`, `jsonDecode()`, JSON parsing
- `SharedPreferences` for storing tokens and settings
- Flutter localization: the project uses a custom `AppLocalizations` class
- Flutter Web limitations: `sqflite` and `path_provider` do not work on web
- `kIsWeb` — always check this before calling any SQLite method

## Setup (Run Once)

```powershell
# Step 1 — Navigate to the Flutter app folder
cd "c:\Users\Computer Arena\OneDrive\TOOBA INDUSTRY DOCUMENTS\disaster_dss\app"

# Step 2 — Install Flutter packages
flutter pub get

# Step 3 — Verify no analysis errors
flutter analyze --no-pub
# Expected output: No issues found!
```

## Run the App

**In Chrome (web):**
```powershell
cd "c:\Users\Computer Arena\OneDrive\TOOBA INDUSTRY DOCUMENTS\disaster_dss\app"
flutter run -d chrome --web-port 8080 --dart-define=BACKEND_URL=http://127.0.0.1:8001 --no-pub
```
App opens at: http://localhost:8080

**On Android emulator or device:**
```powershell
flutter run --dart-define=BACKEND_URL=http://10.0.2.2:8001 --no-pub
```

**On a physical Android device (replace IP with your machine's LAN IP):**
```powershell
flutter run --dart-define=BACKEND_URL=http://192.168.1.x:8001 --no-pub
```

## Verify No Errors Before Committing

```powershell
cd "c:\Users\Computer Arena\OneDrive\TOOBA INDUSTRY DOCUMENTS\disaster_dss\app"
flutter analyze --no-pub
# Must say: No issues found!
```

## Your Files

### Core layer (shared infrastructure)

| File | What it does |
|------|-------------|
| `app/lib/main.dart` | App entry point, startup, routing |
| `app/lib/core/config/app_config.dart` | Backend URL config (uses `--dart-define=BACKEND_URL`) |
| `app/lib/core/theme/app_theme.dart` | All colours, typography, button/card/input styles |
| `app/lib/core/localization/app_localizations.dart` | All UI strings in English, Urdu, Roman Urdu |
| `app/lib/core/providers/language_provider.dart` | Language switching (`en`, `ur`, `ru`) |
| `app/lib/core/providers/app_state_provider.dart` | Online/offline detection |
| `app/lib/core/services/auth_service.dart` | All HTTP calls for register and login |
| `app/lib/core/local_db/database_helper.dart` | SQLite access (knowledge + hazard databases) |
| `app/lib/core/retrieval/keyword_retriever.dart` | Offline keyword search over SQLite |
| `app/lib/core/retrieval/roman_urdu_normalizer.dart` | Roman Urdu spelling variant expansion |
| `app/lib/core/rules_engine/hazard_rules.dart` | Deterministic flood/landslide classifier |

### Feature screens (one file per screen)

| File | Screen |
|------|--------|
| `app/lib/features/onboarding/onboarding_screen.dart` | First-run 3-page intro |
| `app/lib/features/auth/login_screen.dart` | Login form |
| `app/lib/features/auth/signup_screen.dart` | Registration form |
| `app/lib/features/dashboard/dashboard_screen.dart` | Main shell with bottom navigation |
| `app/lib/features/chat/chat_screen.dart` | Offline Q&A (SQLite keyword search) |
| `app/lib/features/map/hazard_map_screen.dart` | GPS + hazard level indicator |
| `app/lib/features/alerts/alerts_screen.dart` | Alert list (SQLite cache + backend sync) |
| `app/lib/features/safety/safety_checklist_screen.dart` | Go-bag and preparedness checklists |
| `app/lib/features/profile/profile_screen.dart` | Language, status, offline package info |
| `app/lib/features/simulator/scenario_simulator_screen.dart` | Demo scenario runner |

### Assets

| Path | Contents |
|------|----------|
| `app/assets/offline_package/knowledge.sqlite` | Official advisory chunks (76 KB seed) |
| `app/assets/offline_package/hazard_grid.sqlite` | 10,000 hazard cells, Chitral (2 MB) |
| `app/web/` | Flutter Web entry point and icons |

## Backend URL Configuration

The backend URL is **not hardcoded**. It comes from `app_config.dart`:

```dart
// app/lib/core/config/app_config.dart
static String get backendUrl {
  if (_customUrl.isNotEmpty) return _customUrl;   // from --dart-define
  if (kIsWeb) return 'http://localhost:8000';      // Flutter Web
  return 'http://10.0.2.2:8000';                  // Android emulator
}
```

To use a custom URL pass it at build/run time:
```powershell
flutter run --dart-define=BACKEND_URL=http://your-server:8001
```

**Never hardcode `10.0.2.2` or `localhost` directly in a screen file.**
Always import and use `AppConfig.backendUrl`.

## Authentication Flow

```
SignupScreen
  → AuthService.register(name, email, password)
    → POST /auth/register → 201 UserResponse
    → AuthService.login(email, password) [called automatically after register]
      → POST /auth/login → 200 TokenResponse
        → AuthService.saveSession(data)
          → SharedPreferences stores: auth_token, user_name, user_email, is_logged_in

LoginScreen
  → AuthService.login(email, password)
    → POST /auth/login → 200 TokenResponse
      → AuthService.saveSession(data)
        → navigate to /dashboard

Logout (ProfileScreen)
  → AuthService.logout()
    → SharedPreferences clears: auth_token, is_logged_in
      → navigate to /login
```

## Offline vs Online Behavior

| Feature | Offline (no internet) | Online (connected) |
|---------|----------------------|-------------------|
| Chat / Q&A | SQLite keyword search — works fully | Same (SQLite only — by design) |
| Hazard map | SQLite grid lookup — works fully | Same (no backend needed) |
| Alerts | Shows cached local alerts | Syncs fresh alerts from backend |
| Auth | Not available (needs backend) | Full register + login |
| Language switch | Works everywhere | Works everywhere |

**Key rule:** Always check `kIsWeb` before calling any SQLite method.
Web does not have sqflite. All database methods already have this guard —
do not remove it.

## Localization — How to Add or Change Strings

All UI text is in `app/lib/core/localization/app_localizations.dart`.
The file has a `_strings` map with three sections: `en`, `ur`, `ru`.

To add a new string:
1. Add the key + value in all three language sections
2. Add a getter method at the bottom of the class
3. Use `AppLocalizations.of(context).yourNewKey` in any widget

Do not hardcode English text directly in widgets. All user-visible text
must go through `AppLocalizations`.

## Colours and Styling

All colours are defined as constants in `AppColors` inside `app_theme.dart`.

| Constant | Hex | Use |
|----------|-----|-----|
| `AppColors.primary` | `#00695C` | Buttons, active elements |
| `AppColors.hazardHigh` | `#D32F2F` | HIGH hazard, critical alerts |
| `AppColors.hazardMedium` | `#F57C00` | MEDIUM hazard, warnings |
| `AppColors.hazardLow` | `#388E3C` | LOW hazard, success states |
| `AppColors.accent` | `#FFA000` | Disclaimers, info notices |
| `AppColors.textMuted` | `#757575` | Secondary text, labels |

**Never use raw hex colours in widgets.** Always use `AppColors.constant`.

Use `.withValues(alpha: 0.x)` — **not** `.withOpacity(x)` (deprecated in Flutter 3.32+).

## What You Can Safely Change

- Any screen layout, padding, visual design
- Add new widgets inside existing screen files
- Improve error messages shown to users
- Add new localization strings (in all three languages)
- Add new checklist items to `safety_checklist_screen.dart`
- Add new Roman Urdu variants in `roman_urdu_normalizer.dart`

## What You Must Not Break

- `AppConfig.backendUrl` — never hardcode URLs in screen files
- `kIsWeb` guards in `database_helper.dart` and `main.dart` — web will crash without them
- `AppLocalizations` keys — do not remove existing keys (other screens use them)
- `AuthService.saveSession()` — must receive a `TokenResponse` object (with `access_token`)
- `alerts_screen.dart` JSON parsing — `decoded['alerts']` must remain as-is
- `HazardRules` thresholds — must stay in sync with the Python pipeline values
- `flutter analyze --no-pub` must return **No issues found** before every commit

## Handing Off to Backend Developer

- If you change what JSON fields you expect from the backend, tell the backend
  developer first — they need to update the Pydantic schema
- Use this to add only your Flutter files to git:

```powershell
git add app/
git commit -m "feat(ui): describe your change here"
git push origin master
```

---

---

# Shared Rules for Both Developers

1. **Run your validation command before every commit** — backend: `validate_backend.py`; frontend: `flutter analyze --no-pub`

2. **Never commit `*.sqlite` database files** — they are in `.gitignore` and are generated locally by the pipeline

3. **Never commit the `.venv/` folder** — it is in `.gitignore`

4. **Never commit secrets** — `SECRET_KEY`, `ADMIN_API_KEY`, passwords, tokens

5. **Coordinate before changing API schemas** — a field rename on the backend
   means a code change on the frontend, and vice versa

6. **Branch naming:**
   - `backend/your-feature-name` for backend work
   - `frontend/your-feature-name` for Flutter work
   - Merge to `master` only after validation passes

7. **Commit message format:**
   ```
   backend: short description of what changed
   feat(ui): short description of what changed
   fix(auth): short description of what changed
   ```

---

## Quick Reference Card

### Backend
```powershell
# Start
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
# Test
python validate_backend.py
# API docs
# Open: http://127.0.0.1:8001/docs
```

### Frontend
```powershell
# Run in Chrome
cd app
flutter run -d chrome --web-port 8080 --dart-define=BACKEND_URL=http://127.0.0.1:8001 --no-pub
# Analyze
flutter analyze --no-pub
```

### One-command full demo
```powershell
# From project root
.\run_demo.ps1
```
