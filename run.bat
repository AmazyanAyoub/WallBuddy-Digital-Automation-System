@echo off
cd /d "%~dp0"

echo ================================
echo  WallBuddy - Running Pipeline
echo ================================

if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv not found. Please run install_packages.bat first.
    pause
    exit /b 1
)

set PYTHON=venv\Scripts\python.exe

%PYTHON% main.py

echo.
echo Done! Check the OUTPUT folder for results.
pause
