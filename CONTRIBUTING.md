# Contributing to Disaster DSS

Thank you for contributing to an offline-first disaster preparedness tool for communities in Chitral, KP.

---

## Local Environment Setup

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ (3.11 recommended) | Pipeline, backend, evaluation |
| Flutter SDK | 3.x | Mobile app |
| Android SDK | API 21+ | Android target |
| Android Studio | Latest stable | Emulator, NDK, CMake |
| Git | Any recent | Version control |

### 1 — Clone and enter the repo

```bash
git clone <repo-url>
cd disaster_dss
```

### 2 — Python virtual environment

```powershell
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3 — Build the offline databases (pipeline)

Run once to generate `offline_package/knowledge.sqlite` and `offline_package/hazard_grid.sqlite`:

```bash
# Full pipeline (PDF extract → chunk → embed → SQLite → GIS grid)
python pipeline/run_pipeline.py

# Skip the embedding step on slow machines (embeddings are backend-only):
python pipeline/run_pipeline.py --skip-embed

# Skip GIS if you don't have rasterio/geopandas installed (uses synthetic terrain):
python pipeline/run_pipeline.py --skip-gis
```

The pipeline automatically copies both `.sqlite` files into `app/assets/offline_package/`.

### 4 — Add real official PDFs (optional but recommended)

Place NDMA / PDMA KP / PMD PDF advisories in `data/raw/` and re-run the pipeline.  
The `pipeline/rag/extract.py` script auto-detects source organisations from filenames.

### 5 — Flutter app

```bash
cd app
flutter pub get
flutter run              # requires connected device or running emulator
flutter analyze          # must pass before any commit
flutter test             # must pass before any commit
```

#### Common Windows build issues

| Error | Fix |
|-------|-----|
| `CMake not found` | Install CMake via Android Studio SDK Manager → SDK Tools |
| `NDK not found` | Install NDK (Side by side) via Android Studio SDK Manager |
| `Gradle sync failed` | Run `flutter clean` then `flutter pub get` |
| `adb not recognised` | Add `%ANDROID_HOME%\platform-tools` to PATH |

### 6 — Run the backend (optional)

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### 7 — Run evaluation

```bash
# First build the pipeline to get knowledge.sqlite, then:
python evaluation/retrieval_eval.py --k 5

# Generate a fresh ground truth template (if adding new chunks):
python evaluation/retrieval_eval.py --create-gt
```

---

## Branch and Commit Guidelines

| Branch | Purpose |
|--------|---------|
| `main` | Always deployable. No direct commits. |
| `feature/<name>` | New features |
| `fix/<name>` | Bug fixes |
| `data/<name>` | Pipeline or data changes |
| `docs/<name>` | Documentation only |

**Commit message format:**

```
<type>(<scope>): <short description>

[optional body]
```

Types: `feat`, `fix`, `data`, `docs`, `test`, `refactor`, `chore`

Examples:
```
feat(chat): add multi-turn conversation memory
fix(retrieval): handle empty query tokens gracefully
data(pipeline): add PDMA KP 2024 landslide advisory
docs(readme): update setup instructions for Windows
```

---

## Pre-Push Checklist

Before pushing any branch, confirm all of the following:

- [ ] `flutter analyze` exits with zero issues
- [ ] `flutter test` exits with zero failures
- [ ] `python evaluation/retrieval_eval.py --k 5` runs without error
- [ ] No secrets, API keys, or `.sqlite` database files are staged (`git status`)
- [ ] `offline_package/` and `data/raw/` are in `.gitignore` and not staged
- [ ] Commit message follows the format above
- [ ] New features have at least one corresponding test or evaluation query

---

## What to Gitignore

The following are already in `.gitignore` and must never be committed:

```
offline_package/*.sqlite
data/raw/*.pdf
data/extracted/
data/chunks/
data/embeddings/
.venv/
__pycache__/
*.pyc
backend/disaster_dss_backend.sqlite
app/assets/offline_package/*.sqlite
```

If you are adding new large data files, add them to `.gitignore` before staging.

---

## Adding New Knowledge Sources

1. Place the official PDF in `data/raw/`
2. Add a filename pattern + metadata entry to `SOURCE_REGISTRY` in `pipeline/rag/extract.py`
3. Re-run `python pipeline/run_pipeline.py`
4. Add evaluation queries for the new content to `data/ground_truth_eval.json`
5. Re-run evaluation and confirm P@5 does not regress

---

## Adding New Languages

1. Add translations to the `_strings` map in `app/lib/core/localization/app_localizations.dart`
2. Add the new locale to `supportedLocales` and `_AppLocalizationsDelegate.isSupported()`
3. Add the language to `LanguageProvider.supportedLanguages`
4. Add spelling variant entries to `RomanUrduNormalizer._variants` if applicable
5. Add evaluation queries in the new language to `data/ground_truth_eval.json`

---

## Core Design Constraints (Do Not Violate)

These constraints are not preferences — they are the system's trust guarantees:

1. **Never generate facts.** The chat/retrieval system must only return verified official content. Do not add any LLM that can invent answers.
2. **Always show source.** Every answer must display `source_org`, `pub_date`, and `evidence_level`.
3. **Always label the hazard indicator.** The GPS hazard level must always be accompanied by the indicator disclaimer. Never present it as a prediction.
4. **Offline first.** Every core feature must work with the device in airplane mode. Online features are enhancements, not requirements.
5. **Language parity.** Features must not silently degrade in Urdu or Roman Urdu without transparent reporting in the evaluation output.

---

## Contributors

- Tooba Iqbal
- Kiran Shams
- Manahill Khitab
