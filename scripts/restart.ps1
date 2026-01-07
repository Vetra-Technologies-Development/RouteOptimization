# Restart script for Route Optimization API (PowerShell)
# Usage: .\scripts\restart.ps1

$ErrorActionPreference = "Stop"

Write-Host "Restarting Route Optimization API..." -ForegroundColor Cyan

# Stop the server
& "$PSScriptRoot\stop.ps1"

# Wait a moment for processes to terminate
Start-Sleep -Seconds 2

# Start the server
& "$PSScriptRoot\start.ps1"

