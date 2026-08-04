@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run start_worldbuilder.bat first.
  pause
  exit /b 1
)
title Worldbuilder AI Worker
echo Dedicated worker mode. Disable the built-in worker on the API process first.
".venv\Scripts\python.exe" -m worldbuilder_core.embedding_worker
