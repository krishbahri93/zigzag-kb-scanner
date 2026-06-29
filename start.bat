@echo off
setlocal
cd /d "%~dp0"
title ZigZag Scanner (local)

REM ============================================================
REM  ZigZag Scanner - one-click launcher (Windows).
REM  Just DOUBLE-CLICK this file.
REM    - The first time, it installs everything (a few minutes).
REM    - After that, it just starts the app and opens your browser.
REM  To STOP the app, close this black window.
REM  If anything ever looks broken: close this window and
REM  double-click start.bat again. That fixes almost everything.
REM ============================================================

REM --- If the app is already running, just open the browser (never start a 2nd copy). ---
netstat -ano | findstr "127.0.0.1:8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo The app is already running - opening your browser...
  start "" "http://127.0.0.1:8000"
  exit /b 0
)

REM --- One-time setup: build the environment + install, only if it isn't there yet. ---
if not exist "venv\Scripts\python.exe" (
  echo.
  echo First-time setup: creating the environment and installing.
  echo This downloads some packages and takes a few minutes. Please wait...
  echo.
  python -m venv venv
  if errorlevel 1 (
    echo.
    echo ============================================================
    echo  ERROR: Python was not found on this computer.
    echo  1^) Install Python 3.10 or newer from:
    echo        https://www.python.org/downloads/
    echo  2^) During install, TICK the box "Add Python to PATH".
    echo  3^) Then double-click start.bat again.
    echo ============================================================
    pause
    exit /b 1
  )
  call "venv\Scripts\activate.bat"
  python -m pip install --upgrade pip >nul
  pip install -e ".[india,app]"
  if errorlevel 1 (
    echo.
    echo ERROR: install failed. Check your internet connection,
    echo then double-click start.bat again to retry.
    pause
    exit /b 1
  )
) else (
  call "venv\Scripts\activate.bat"
)

REM --- Open the browser ~3 seconds after the server starts, then run the server. ---
start "" /b powershell -NoProfile -Command "Start-Sleep 3; Start-Process 'http://127.0.0.1:8000'" >nul 2>&1
echo.
echo ============================================================
echo  Starting... a browser tab will open in a few seconds.
echo  KEEP THIS WINDOW OPEN while you use the app.
echo  Close this window to stop the app.
echo ============================================================
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
