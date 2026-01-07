@echo off
REM Simple wrapper to stop the API server on Windows
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"

