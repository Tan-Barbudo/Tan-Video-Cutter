@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Primero debes ejecutar install_windows.bat
  pause
  exit /b 1
)
.venv\Scripts\python.exe src\main.py
if errorlevel 1 pause
