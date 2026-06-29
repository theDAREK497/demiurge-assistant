@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Worldbuilder Core

echo.
echo ==========================================
echo   Worldbuilder Core starter
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    python -m venv .venv
  )
)

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Cannot find Python in .venv. Install Python 3.12+ and try again.
  pause
  exit /b 1
)

"%PY%" -m pip show fastapi >nul 2>&1
if errorlevel 1 (
  echo Installing project dependencies...
  "%PY%" -m pip install -e ".[dev]"
  if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
  )
)

echo Choose server mode:
echo   1 - Local only, this computer
echo   2 - LAN mode, players can connect by IP if firewall/port allows it
set /p "WB_MODE=Mode [1]: "
if "%WB_MODE%"=="2" (
  set "WB_HOST=0.0.0.0"
) else (
  set "WB_HOST=127.0.0.1"
)

set /p "WB_PORT=Port [8000]: "
if "%WB_PORT%"=="" set "WB_PORT=8000"

set /p "WB_BASE=LM Studio Base URL [http://127.0.0.1:1234/v1]: "
if "%WB_BASE%"=="" set "WB_BASE=http://127.0.0.1:1234/v1"
set "WORLDBUILDER_LLM_BASE_URL=%WB_BASE%"

set /p "WB_MODEL=Model name loaded in LM Studio [leave empty to keep default/UI settings]: "
if not "%WB_MODEL%"=="" set "WORLDBUILDER_LLM_MODEL=%WB_MODEL%"

set "WB_OPEN_URL=http://127.0.0.1:%WB_PORT%/app/?role=master"
echo.
echo Local UI:
echo   %WB_OPEN_URL%

if "%WB_HOST%"=="0.0.0.0" (
  for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4.*"') do (
    set "WB_LAN_IP=%%A"
    goto :got_ip
  )
  :got_ip
  set "WB_LAN_IP=%WB_LAN_IP: =%"
  if not "%WB_LAN_IP%"=="" (
    echo Player URL on LAN:
    echo   http://%WB_LAN_IP%:%WB_PORT%/app/?role=player
    echo If this IP looks wrong, run ipconfig and use your real Wi-Fi/Ethernet IPv4.
  )
  echo.
  echo Windows Firewall may ask for permission. Allow it for LAN play.
)

echo.
echo Note: settings saved in the UI override these startup defaults.
echo Starting server. Close this window or press Ctrl+C to stop.
echo.
start "" "%WB_OPEN_URL%"
"%PY%" -m uvicorn worldbuilder_core.main:app --host %WB_HOST% --port %WB_PORT%

echo.
echo Server stopped.
pause
