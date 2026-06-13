@echo off
setlocal
cd /d "%~dp0"
pythonw.exe -m desktop.app
if errorlevel 1 (
  python.exe -m desktop.app
)
exit /b %errorlevel%

