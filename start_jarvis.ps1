# Run from PowerShell: powershell -ExecutionPolicy Bypass -File .\start_jarvis.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv\Scripts\python.exe)) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { throw "Install Python 3.11 or 3.12 from python.org, with Python Launcher enabled." }
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { py -3 -m venv .venv }
}
if (-not (Test-Path .venv\.deps-installed)) {
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip bootstrapping failed" }
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    New-Item -ItemType File -Path .venv\.deps-installed -Force | Out-Null
}
& .\.venv\Scripts\python.exe main.py
if ($LASTEXITCODE -ne 0) { throw "JARVIS exited with an error; try python doctor.py for diagnostics" }
