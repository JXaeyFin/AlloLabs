@echo off
setlocal
call "%~dp0restart-dashboard.bat"
exit /b %errorlevel%
