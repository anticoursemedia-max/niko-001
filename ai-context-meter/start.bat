@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^) and run this file again.
  pause
  exit /b 1
)
python -c "import pywinauto" >nul 2>nul || python -m pip install --quiet pywinauto
start "" pythonw meter.py
