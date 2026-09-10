# ============================================================
# Disaster DSS — Local Demo Launcher
# Usage: .\run_demo.ps1
# Starts: FastAPI backend (port 8000) + Flutter Web (port 8080)
# Stop:   Press Ctrl+C in each terminal, or close the windows
# ============================================================

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BACKEND_DIR = Join-Path $ROOT "backend"
$APP_DIR = Join-Path $ROOT "app"

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   Disaster DSS — Local Demo" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project root : $ROOT" -ForegroundColor Gray
Write-Host ""

# ── 1. Check Python ──────────────────────────────────────────────────────────
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "ERROR: python not found in PATH." -ForegroundColor Red
    exit 1
}
$pyver = & python --version 2>&1
Write-Host "Python       : $pyver" -ForegroundColor Gray

# ── 2. Check aiosqlite ───────────────────────────────────────────────────────
$aio = & python -c "import aiosqlite; print(aiosqlite.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing aiosqlite..." -ForegroundColor Yellow
    & python -m pip install aiosqlite==0.20.0 --quiet
}

# ── 3. Check Flutter ─────────────────────────────────────────────────────────
$fl = Get-Command flutter -ErrorAction SilentlyContinue
if (-not $fl) {
    Write-Host "ERROR: flutter not found in PATH." -ForegroundColor Red
    exit 1
}
$flver = & flutter --version 2>&1 | Select-Object -First 1
Write-Host "Flutter      : $flver" -ForegroundColor Gray
Write-Host ""

# ── 4. Start FastAPI backend in a new window ─────────────────────────────────
Write-Host "Starting FastAPI backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
$backendCmd = "cd '$ROOT'; python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level info; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# Give backend a moment to start
Start-Sleep -Seconds 3

# ── 5. Verify backend is up ──────────────────────────────────────────────────
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method GET -TimeoutSec 5
    Write-Host "Backend      : OK (status=$($health.status), version=$($health.version))" -ForegroundColor Green
} catch {
    Write-Host "Backend      : Not responding yet — it may still be starting." -ForegroundColor Yellow
}

# ── 6. Flutter pub get ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Running flutter pub get..." -ForegroundColor Yellow
Push-Location $APP_DIR
& flutter pub get --quiet
Pop-Location

# ── 7. Start Flutter Web in a new window ─────────────────────────────────────
Write-Host "Starting Flutter Web on http://localhost:8080 ..." -ForegroundColor Green
$flutterCmd = "cd '$APP_DIR'; flutter run -d web-server --web-port 8080 --dart-define=BACKEND_URL=http://127.0.0.1:8000; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $flutterCmd

# ── 8. Print summary ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   DEMO IS STARTING" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend API  : http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  API Docs     : http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  Flutter Web  : http://localhost:8080" -ForegroundColor White
Write-Host ""
Write-Host "  Flutter Web takes ~30-60 seconds to compile." -ForegroundColor Gray
Write-Host "  Open http://localhost:8080 in your browser." -ForegroundColor Gray
Write-Host ""
Write-Host "  To stop: close both PowerShell windows." -ForegroundColor Gray
Write-Host ""
Write-Host "  Quick API test (run in another terminal):" -ForegroundColor Gray
Write-Host '  Invoke-RestMethod http://127.0.0.1:8000/health' -ForegroundColor DarkGray
Write-Host ""
