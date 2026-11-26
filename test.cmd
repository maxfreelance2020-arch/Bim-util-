@echo off
setlocal
set PYTHONUTF8=1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\test.ps1" %*
exit /b %errorlevel%
