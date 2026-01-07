@echo off
REM Simple wrapper to start the API server on Windows
REM This script runs the PowerShell start script with execution policy bypass

echo Starting Route Optimization API...
echo.

REM Check if PowerShell is available
where powershell.exe >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: PowerShell is not available.
    echo Please run: scripts\start.ps1
    pause
    exit /b 1
)

REM Run the PowerShell script
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Script exited with error code %ERRORLEVEL%
    pause
)

