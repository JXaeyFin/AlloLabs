@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-dashboard.ps1" -Restart
if errorlevel 1 pause
