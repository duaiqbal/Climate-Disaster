# 🚀 ChitralSafe — Complete Setup Guide for Team Members

This guide covers everything you need to run the project locally on your machine.

---

## 📋 Prerequisites

Before starting, install these tools:

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11 or 3.12 | https://python.org/downloads |
| Flutter SDK | 3.x | https://docs.flutter.dev/get-started/install |
| Git | Latest | https://git-scm.com |
| Chrome | Latest | https://google.com/chrome |
| VS Code | Latest (recommended) | https://code.visualstudio.com |
| Ollama | Latest (optional, for AI) | https://ollama.com |

### Verify installations
```bash
python --version       # Should show 3.11.x or 3.12.x
flutter --version      # Should show Flutter 3.x
git --version          # Any recent version
```

---

## 🪟 Windows Setup (Step by Step)

### Step 1 — Clone the project
```powershell
git clone https://github.com/duaiqbal/Climate-Disaster.git
cd Climate-Disaster
```

### Step 2 — Backend Python setup
```powershell
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate

# You should see (.venv) at the start of your prompt
# Install all dependencies
pip install -r requirements.txt
```

> ⚠️ If pip install fails on torch/sentence-transformers, run:
> `pip install -r requirements.txt --timeout 300`

### Step 3 — Configure environment
```powershell
# Copy the template
copy .env.example .env

# Open in notepad to edit (or use VS Code)
notepad .env
```

For basic local development, the defaults in `.env.example` work fine. Just save as `.env`.

### Step 4 — Start the backend
```powershell
# Make sure you're in backend/ with (.venv) active
python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8002
INFO:     Application startup complete.
```

✅ Test it: Open http://127.0.0.1:8002/health in browser
✅ API docs: Open http://127.0.0.1:8002/docs in browser

### Step 5 — Start the Flutter app
Open a **new terminal window** (keep backend running):
```powershell
cd Climate-Disaster\app

# Install Flutter dependencies
flutter pub get

# Run in Chrome
flutter run -d chrome --web-port 8080
```

✅ App opens at: http://localhost:8080

---

## 🍎 Mac / Linux Setup (Step by Step)

### Step 1 — Clone the project
```bash
git clone https://github.com/duaiqbal/Climate-Disaster.git
cd Climate-Disaster
```

### Step 2 — Backend Python setup
```bash
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# You should see (.venv) at the start of your prompt
# Install all dependencies
pip install -r requirements.txt
```

### Step 3 — Configure environment
```bash
cp .env.example .env
# Edit with your preferred editor
nano .env
# or: code .env
```

### Step 4 — Start the backend
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload
```

### Step 5 — Start Flutter app
Open a new terminal:
```bash
cd Climate-Disaster/app
flutter pub get
flutter run -d chrome --web-port 8080
```

---

## 🤖 Enable AI Chat (Optional but Recommended)

The chatbot works in offline mode by default (retrieval only).  
To enable full AI responses with Ollama:

### Step 1 — Install Ollama
- Windows/Mac: Download from https://ollama.com
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`

### Step 2 — Pull the model (one time, ~4.7 GB)
```bash
ollama pull llama3
```

### Step 3 — Start Ollama
```bash
ollama serve
# Runs on http://localhost:11434
```

### Step 4 — Update .env
Open `backend/.env` and change:
```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3
LLM_BASE_URL=http://localhost:11434/v1
```

### Step 5 — Restart backend
Stop and restart the backend server. Now AI chat will use Llama3!

---

## ⚡ One-Click Setup Scripts

### Windows (PowerShell)
```powershell
# Run from project root
.\setup.ps1
```

### Mac / Linux (Bash)
```bash
# Run from project root
chmod +x setup.sh
./setup.sh
```

These scripts automatically:
- Create Python virtual environment
- Install all dependencies
- Copy `.env.example` to `.env`
- Verify Flutter installation
- Start the backend server

---

## 🔑 Admin API Key

Some endpoints require an admin key (creating alerts, publishing packages, triggering scraper).

Default dev key (in `.env.example`):
```
ADMIN_API_KEY=change-me-to-a-strong-admin-key
```

To use admin endpoints with curl:
```bash
curl -X POST http://127.0.0.1:8002/monitor/run \
  -H "X-Admin-Key: change-me-to-a-strong-admin-key"
```

---

## 🧪 Running Tests

```bash
# Make sure you're in backend/ with .venv active
cd backend
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Mac/Linux

python -m pytest tests/ -v
```

Expected output:
```
122 passed in 29s
```

Run a specific test file:
```bash
python -m pytest tests/test_phase3_rag.py -v
python -m pytest tests/test_alerts.py -v
```

---

## 🗄️ Database

The app uses SQLite by default — no database server needed!

- **App DB** (alerts, users, sync): Auto-created in system TEMP folder
- **Knowledge DB** (NDMA/PDMA docs): `offline_package/knowledge.sqlite`

To rebuild the knowledge database from PDFs:
```bash
cd pipeline
python run_pipeline.py
```

---

## 📱 Build Flutter App for Production

### Web build
```bash
cd app
flutter build web --release
# Output in: app/build/web/
```

Serve with Python (for testing):
```bash
python -m http.server 8080 --directory build/web
```

### Android APK
```bash
flutter build apk --release
# Output: app/build/app/outputs/flutter-apk/app-release.apk
```

---

## 🐛 Troubleshooting

### "No module named 'backend'"
```bash
# Always run pytest from inside the backend/ directory
cd backend
python -m pytest tests/ -v
```

### "CORS error" in browser
Add your URL to `CORS_ORIGINS` in `backend/.env`:
```env
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

### "Port 8002 already in use"
```powershell
# Windows — find and kill the process
netstat -ano | findstr :8002
taskkill /PID <PID_NUMBER> /F
```
```bash
# Mac/Linux
lsof -i :8002
kill -9 <PID>
```

### Flutter "pub get" fails
```bash
flutter clean
flutter pub get
```

### "knowledge.sqlite not found"
The knowledge DB is not included in git (too large). Build it:
```bash
cd pipeline
python run_pipeline.py
```
Or ask a team member for the file directly.

### Backend crashes on startup
```bash
# Check your .env file exists
ls backend/.env

# Check Python version
python --version  # Must be 3.11 or 3.12

# Try reinstalling dependencies
pip install -r requirements.txt --force-reinstall
```

---

## 📞 Need Help?

1. Check this guide again carefully
2. Check `README.md` for API documentation
3. Run tests to verify your setup: `python -m pytest tests/ -v`
4. Ask a team member on WhatsApp group

---

## 🔗 Useful Links

| Resource | URL |
|----------|-----|
| GitHub Repo | https://github.com/duaiqbal/Climate-Disaster |
| Backend API Docs | http://127.0.0.1:8002/docs (when running) |
| Flutter Docs | https://docs.flutter.dev |
| FastAPI Docs | https://fastapi.tiangolo.com |
| Ollama | https://ollama.com |
| NDMA Pakistan | https://ndma.gov.pk |
| PDMA KP | https://pdma.gov.pk |
