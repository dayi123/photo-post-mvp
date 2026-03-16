Param(
  [switch]$SetupOnly,
  [switch]$NoBrowser,
  [string]$Host = "127.0.0.1",
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Get-Python {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    return "py"
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    return "python"
  }
  throw "Python not found. Please install Python 3.11+ and rerun."
}

$Py = Get-Python

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Host "[INFO] Creating virtual environment..."
  & $Py -m venv .venv
}

Write-Host "[INFO] Installing dependencies..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

if ($SetupOnly) {
  Write-Host "[OK] Setup complete."
  exit 0
}

if (-not $NoBrowser) {
  Start-Process "http://$Host`:$Port/ui"
}

Write-Host "[INFO] Starting server at http://$Host`:$Port"
$env:PHOTO_POST_EDITOR = "stub"
& ".venv\Scripts\python.exe" -m uvicorn app.main:app --host $Host --port $Port --reload
