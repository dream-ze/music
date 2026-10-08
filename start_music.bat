@echo off
REM Double-click to start ze music backend (web + API on port 8000).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_api.ps1"
if errorlevel 1 pause
