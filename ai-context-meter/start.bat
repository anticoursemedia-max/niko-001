@echo off
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo Python not found. Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^) and run this file again.
  pause
  exit /b 1
)
%PY% -c "import pywinauto" >nul 2>nul || %PY% -m pip install --quiet pywinauto
start "" %PY%w meter.py
