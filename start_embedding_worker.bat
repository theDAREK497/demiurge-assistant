@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run start_worldbuilder.bat first.
  pause
  exit /b 1
)
title Worldbuilder Embedding Worker
".venv\Scripts\python.exe" -m worldbuilder_core.embedding_worker
