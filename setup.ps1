# ============================================================
# ChitralSafe — Windows Auto Setup Script
# Run from project root: .\setup.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ChitralSafe — Auto Setup Script (Windows)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check Python ──────────────────────────────────────
Write-Host "[1/6] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  ✓ $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Install from https://python.org/downloads" -ForegroundColor Red
    exit 1
}

# ── Step 2: Create virtual environment ───────────────────────
Write-Host "[2/6] Setting up Python virtual environment..." -ForegroundColor Yellow
Set-Location backend

if (-Not (Test-Path ".venv")) {
    python -m venv .venv
    Write-Host "  ✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "  ✓ Virtual environment already exists" -ForegroundColor Green
}

# ── Step 3: Install dependencies ─────────────────────────────
Write-Host "[3/6] Installing Python dependencies..." -ForegroundColor Yellow
Write-Host "  (This may take 2-5 minutes on first run)" -ForegroundColor Gray
.venv\Scripts\pip.exe install -r requirements.txt --quiet
Write-Host "  ✓ All dependencies installed" -ForegroundColor Green

# ── Step 4: Setup .env ────────────────────────────────────────
Write-Host "[4/6] Configuring environment..." -ForegroundColor Yellow
if (-Not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✓ .env created from template" -ForegroundColor Green
    Write-Host "  ℹ  Edit backend\.env to customize settings" -ForegroundColor Cyan
} else {
    Write-Host "  ✓ .env already exists (keeping existing config)" -ForegroundColor Green
}

Set-Location ..

# ── Step 5: Check Flutter ─────────────────────────────────────
Write-Host "[5/6] Checking Flutter..." -ForegroundColor Yellow
try {
    $flutterVersion = flutter --version 2>&1 | Select-Object -First 1
    Write-Host "  ✓ $flutterVersion" -ForegroundColor Green

    Write-Host "  Installing Flutter dependencies..." -ForegroundColor Gray
    Set-Location app
    flutter pub get --suppress-analytics 2>&1 | Out-Null
    Set-Location ..
    Write-Host "  ✓ Flutter dependencies ready" -ForegroundColor Green
} catch {
    Write-Host "  ⚠  Flutter not found. Install from https://docs.flutter.dev/get-started/install" -ForegroundColor Yellow
    Write-Host "  ℹ  Backend will still work without Flutter" -ForegroundColor Cyan
}

# ── Step 6: Done ──────────────────────────────────────────────
Write-Host "[6/6] Setup complete!" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  ✅ Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Start backend:" -ForegroundColor Cyan
Write-Host "     cd backend" -ForegroundColor White
Write-Host "     .venv\Scripts\activate" -ForegroundColor White
Write-Host "     python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload" -ForegroundColor White
Write-Host ""
Write-Host "  2. Start Flutter app (new terminal):" -ForegroundColor Cyan
Write-Host "     cd app" -ForegroundColor White
Write-Host "     flutter run -d chrome --web-port 8080" -ForegroundColor White
Write-Host ""
Write-Host "  3. Open in browser:" -ForegroundColor Cyan
Write-Host "     App  → http://localhost:8080" -ForegroundColor White
Write-Host "     API  → http://127.0.0.1:8002/docs" -ForegroundColor White
Write-Host ""
Write-Host "  4. (Optional) Enable AI chat:" -ForegroundColor Cyan
Write-Host "     Install Ollama: https://ollama.com" -ForegroundColor White
Write-Host "     Run: ollama pull llama3" -ForegroundColor White
Write-Host "     Set LLM_PROVIDER=ollama in backend\.env" -ForegroundColor White
Write-Host ""
Write-Host "  See SETUP.md for detailed instructions and troubleshooting." -ForegroundColor Gray
Write-Host ""
