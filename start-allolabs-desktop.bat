@echo off
setlocal
cd /d "%~dp0"
set "PYW=pythonw.exe"
set "PY=python.exe"
if exist ".venv\Scripts\pythonw.exe" (
  set "PYW=%~dp0.venv\Scripts\pythonw.exe"
  set "PY=%~dp0.venv\Scripts\python.exe"
  set "ALLOLABS_ANALYSIS_PYTHON=%~dp0.venv\Scripts\python.exe"
)
"%PYW%" -m desktop.app
if errorlevel 1 (
  "%PY%" -m desktop.app
)
exit /b %errorlevel%
