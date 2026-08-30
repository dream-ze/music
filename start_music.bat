@echo off
setlocal
cd /d "%~dp0"
set "ACESTEP_PROJECT_ROOT=%~dp0..\ACE-Step-1.5"
set "ACESTEP_LM_BACKEND=pt"
if not exist "%ACESTEP_PROJECT_ROOT%\.venv\Scripts\python.exe" (
  echo ACE-Step environment is missing.
  echo Expected: %ACESTEP_PROJECT_ROOT%\.venv\Scripts\python.exe
  pause
  exit /b 1
)
"%ACESTEP_PROJECT_ROOT%\.venv\Scripts\python.exe" app.py
if errorlevel 1 pause
