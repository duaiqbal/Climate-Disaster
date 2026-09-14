@echo off
title ChitralSafe - Complete Startup
color 0B

echo ================================================
echo    ChitralSafe Disaster Decision Support
echo ================================================
echo.
echo Starting all services...
echo.

REM Step 1: Start Backend
echo [1/2] Starting Backend API (Port 8002)...
cd /d "%~dp0backend"
start "ChitralSafe Backend" /MIN cmd /k "python -m uvicorn main:app --port 8002"

echo Waiting for backend to initialize...
timeout /t 8 /nobreak >nul

REM Step 2: Start Flutter Web
echo.
echo [2/2] Starting Flutter Web App (Port 8080)...
cd /d "%~dp0app"
start "ChitralSafe Flutter" cmd /k "flutter run -d chrome --web-port 8080"

echo.
echo ================================================
echo    ChitralSafe is starting!
echo ================================================
echo.
echo Backend:  http://localhost:8002
echo App:      http://localhost:8080
echo Docs:     http://localhost:8002/docs
echo.
echo Chrome will open automatically in 30 seconds...
echo.
echo Keep both windows running in background.
echo Press any key to close this window (services will continue).
echo ================================================
pause >nul
