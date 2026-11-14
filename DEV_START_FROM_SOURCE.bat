@echo off
:: DEVELOPER SOURCE LAUNCH ONLY; end users require JARVIS-Setup-*.exe instead.
cd /d "%~dp0"
echo THIS IS A SOURCE PROJECT, NOT THE ONE-CLICK WINDOWS INSTALLER.
echo This developer launcher needs Python 3.12 already installed on the BUILD PC.
echo To generate the proper setup EXE, see README.md and GitHub Actions.
echo.
powershell -NoProfile -File "%~dp0start_jarvis.ps1"
if errorlevel 1 echo Source launch failed. Read the error messages above.
pause
