@echo off
setlocal
cd /d "%~dp0"
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo Windows PowerShell is required to BUILD the installer.
  pause
  exit /b 1
)
powershell.exe -NoProfile -File "%~dp0packaging\build_installer.ps1"
if errorlevel 1 (
  echo.
  echo BUILD FAILED. Read the error above. This script is for developers only.
  pause
  exit /b 1
)
echo.
echo Installer is in the dist folder. End users only run JARVIS-Setup-*.exe
pause
