@echo off
cd /d "%~dp0"

echo ======================================
echo   Song Splitter
echo ======================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed on this computer.
  echo Please install it from https://www.python.org/downloads/
  echo ^(tick "Add python to PATH" during install^) then double-click this file again.
  pause
  exit /b 1
)

python install_deps.py
if errorlevel 1 (
  pause
  exit /b 1
)

if not exist "venv" (
  echo Setup did not complete.
  pause
  exit /b 1
)

call venv\Scripts\activate.bat
python app.py
pause
