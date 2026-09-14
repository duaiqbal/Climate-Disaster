@echo off
title ChitralSafe - Stop All Services
color 0C

echo ================================================
echo    Stopping ChitralSafe Services
echo ================================================
echo.

REM Kill Python (Backend)
echo Stopping Backend...
taskkill /F /IM python.exe >nul 2>&1

REM Kill Dart (Flutter)
echo Stopping Flutter...
taskkill /F /IM dart.exe >nul 2>&1

REM Kill Chrome instances from Flutter
echo Closing Chrome...
taskkill /FI "WINDOWTITLE eq ChitralSafe*" /F >nul 2>&1

echo.
echo All services stopped.
echo.
pause
