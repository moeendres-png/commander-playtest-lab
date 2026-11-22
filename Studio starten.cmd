@echo off
rem One-click start of the Commander Studio: double-click this file.
rem It calls scripts\studio_oneclick.ps1 (thin wrapper), which runs the Python logic
rem python -m commander_lab.studio.oneclick. Nothing is installed without a typed "J".
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\studio_oneclick.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo Der Starter wurde mit Code %RC% beendet. Die Meldungen oben sagen, was fehlt.
  pause
)
endlocal & exit /b %RC%
