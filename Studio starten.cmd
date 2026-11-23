@echo off
rem One-click start of the Commander Studio: double-click this file.
rem It calls scripts\studio_oneclick.ps1 (thin wrapper), which runs the Python logic
rem python -m commander_lab.studio.oneclick. Programs (Python, Java) are never installed
rem without a typed "J"; Python packages in .venv and the engine download run without a
rem question because they are what the starter is for.
rem The whole body is one block: cmd reads a batch file by position, and an update while
rem the starter runs may change this file; a block is parsed completely before it runs.
setlocal
(
  chcp 65001 >nul
  set "PYTHONUTF8=1"
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\studio_oneclick.ps1" %*
  rem "if errorlevel 1" misses negative codes, and %ERRORLEVEL% would expand when the block
  rem is read; both errorlevel tests together catch every non-zero code at run time.
  set "STUDIO_FEHLER="
  if errorlevel 1 set "STUDIO_FEHLER=1"
  if not errorlevel 0 set "STUDIO_FEHLER=1"
  if defined STUDIO_FEHLER (
    echo.
    echo Der Starter wurde mit einem Fehlercode beendet. Die Meldungen oben sagen, was fehlt.
    pause
  )
  exit /b
)
