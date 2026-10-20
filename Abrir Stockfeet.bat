@echo off
title Stockfeet
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtualenv and installing Stockfeet...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -e . -q
)

:: Use console python so startup errors are visible (pythonw hides them).
".venv\Scripts\python.exe" -m stockfeet play
if errorlevel 1 (
  echo.
  echo Stockfeet failed to start. See the message above.
  pause
)
