@echo off
setlocal enabledelayedexpansion

REM One-click launcher for Windows newcomers.
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

set "PY_CMD="
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY_CMD=py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PY_CMD=python"
  )
)

if "%PY_CMD%"=="" (
  echo [ERROR] Python not found. Install Python 3.11+ and re-run.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Creating virtual environment...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo [INFO] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install dependencies.
  pause
  exit /b 1
)

if /i "%~1"=="--setup-only" (
  echo [OK] Setup complete.
  exit /b 0
)

echo [INFO] Starting server at http://127.0.0.1:8000
start "" "http://127.0.0.1:8000/ui"

set "PHOTO_POST_EDITOR=stub"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

endlocal
