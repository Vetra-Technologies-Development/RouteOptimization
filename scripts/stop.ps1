# Stop script for Route Optimization API (PowerShell)
# Usage: .\scripts\stop.ps1

$ErrorActionPreference = "Stop"

Write-Host "Stopping Route Optimization API..." -ForegroundColor Yellow

# Find and kill uvicorn processes
$processes = Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*uvicorn*" } -ErrorAction SilentlyContinue

if ($processes) {
    foreach ($proc in $processes) {
        try {
            $procInfo = Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)" | Select-Object CommandLine
            if ($procInfo.CommandLine -like "*main:app*") {
                Write-Host "Stopping process $($proc.Id)..." -ForegroundColor Cyan
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            # Process might have already terminated
        }
    }
    Write-Host "Server stopped." -ForegroundColor Green
} else {
    # Alternative: Find by port (default 8000)
    $port = if ($env:PORT) { $env:PORT } else { "8000" }
    Write-Host "Checking for processes on port $port..." -ForegroundColor Cyan
    
    $netstat = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
    if ($netstat) {
        $pid = ($netstat -split '\s+')[-1]
        if ($pid) {
            Write-Host "Stopping process on port $port (PID: $pid)..." -ForegroundColor Cyan
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "Server stopped." -ForegroundColor Green
        }
    } else {
        Write-Host "No server process found running." -ForegroundColor Yellow
    }
}

