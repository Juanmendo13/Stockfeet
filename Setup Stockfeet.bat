@echo off
title Stockfeet — first-time setup
cd /d "%~dp0"

echo.
echo  Stockfeet — powered by Leela Chess Zero (lc0)
echo  https://lczero.org/  (GPL-3.0-or-later)
echo  Stockfeet app code is MIT. lc0 is a separate engine.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating virtualenv...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo Python 3.11+ is required. Install from https://www.python.org/downloads/
    pause
    exit /b 1
  )
  echo [2/3] Installing Stockfeet...
  ".venv\Scripts\python.exe" -m pip install -U pip -q
  ".venv\Scripts\python.exe" -m pip install -e . -q
) else (
  echo [1/3] Virtualenv OK
  echo [2/3] Ensuring Stockfeet install...
  ".venv\Scripts\python.exe" -m pip install -e . -q
)

echo [3/3] Downloading official lc0 (Windows CPU try build)...
".venv\Scripts\python.exe" -m stockfeet setup-lc0
if errorlevel 1 (
  echo.
  echo lc0 download failed. You can still open the hub for puzzles, then retry.
  echo Manual download: https://lczero.org/play/download/
  pause
)

echo.
echo Starting Stockfeet...
call "%~dp0Abrir Stockfeet.bat"
