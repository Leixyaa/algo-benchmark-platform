@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0manual_up_desktop.ps1" %*
endlocal
