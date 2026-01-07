@echo off
REM Simple wrapper to restart the API server on Windows
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\restart.ps1"

