# Start script for Route Optimization API (PowerShell)
# Usage: .\scripts\start.ps1

$ErrorActionPreference = "Continue"

Write-Host "Starting Route Optimization API..." -ForegroundColor Green

# Check if Python is available - try multiple commands
$pythonCmd = $null
$pythonVersion = $null

# Try different Python commands in order of preference
$pythonCommands = @("py", "python", "python3")

foreach ($cmd in $pythonCommands) {
    try {
        # Use Start-Process or direct execution with better error handling
        $process = Start-Process -FilePath $cmd -ArgumentList "--version" -NoNewWindow -Wait -PassThru -RedirectStandardOutput "temp_py_version.txt" -RedirectStandardError "temp_py_error.txt" -ErrorAction SilentlyContinue
        if (Test-Path "temp_py_version.txt") {
            $versionOutput = Get-Content "temp_py_version.txt" -Raw
            Remove-Item "temp_py_version.txt" -ErrorAction SilentlyContinue
            Remove-Item "temp_py_error.txt" -ErrorAction SilentlyContinue
            if ($versionOutput -and $versionOutput -match "Python") {
                $pythonCmd = $cmd
                $pythonVersion = $versionOutput.Trim()
                break
            }
        }
    } catch {
        # Try direct execution as fallback
        try {
            $versionOutput = & $cmd --version 2>&1
            if ($versionOutput -and ($versionOutput -match "Python" -or $versionOutput.ToString() -match "Python")) {
                $pythonCmd = $cmd
                $pythonVersion = $versionOutput.ToString().Trim()
                break
            }
        } catch {
            # Continue to next command
            continue
        }
    }
}

# If still not found, try to find Python in common locations
if (-not $pythonCmd) {
    Write-Host "Searching for Python in common installation paths..." -ForegroundColor Yellow
    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python*",
        "$env:ProgramFiles\Python*",
        "$env:ProgramFiles(x86)\Python*",
        "$env:APPDATA\Python\Python*"
    )
    
    foreach ($pathPattern in $commonPaths) {
        $foundPython = Get-ChildItem -Path $pathPattern -Directory -ErrorAction SilentlyContinue | 
            ForEach-Object { Get-ChildItem -Path "$($_.FullName)\python.exe" -ErrorAction SilentlyContinue } | 
            Select-Object -First 1
        if ($foundPython) {
            $testCmd = $foundPython.FullName
            try {
                $versionOutput = & $testCmd --version 2>&1
                if ($versionOutput -and ($versionOutput -match "Python" -or $versionOutput.ToString() -match "Python")) {
                    $pythonCmd = $testCmd
                    $pythonVersion = $versionOutput.ToString().Trim()
                    Write-Host "Found Python at: $pythonCmd" -ForegroundColor Cyan
                    break
                }
            } catch {
                continue
            }
        }
    }
}

# Final check
if (-not $pythonCmd -or -not $pythonVersion) {
    Write-Host "Error: Python not found. Please install Python 3.11 or later." -ForegroundColor Red
    Write-Host "You can download Python from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Or install from Microsoft Store: https://apps.microsoft.com/store/detail/python-311/9NRWMJP3717K" -ForegroundColor Yellow
    exit 1
}

Write-Host "Using Python: $pythonVersion" -ForegroundColor Cyan

# Check if virtual environment exists
if (Test-Path "venv") {
    Write-Host "Activating virtual environment..." -ForegroundColor Cyan
    if (Test-Path "venv\Scripts\Activate.ps1") {
        & "venv\Scripts\Activate.ps1"
    } else {
        Write-Host "Virtual environment found but activation script missing. Recreating..." -ForegroundColor Yellow
        Remove-Item -Path "venv" -Recurse -Force -ErrorAction SilentlyContinue
        & $pythonCmd -m venv venv
        & "venv\Scripts\Activate.ps1"
    }
} else {
    Write-Host "Virtual environment not found. Creating one..." -ForegroundColor Yellow
    & $pythonCmd -m venv venv
    if (Test-Path "venv\Scripts\Activate.ps1") {
        & "venv\Scripts\Activate.ps1"
    } else {
        Write-Host "Error: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    & pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Some dependencies may have failed to install. Continuing..." -ForegroundColor Yellow
    }
}

# Check if required packages are installed, install if missing
Write-Host "Verifying required packages..." -ForegroundColor Cyan
$requiredPackages = @("fastapi", "uvicorn", "pydantic")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    try {
        $packageCheck = & pip show $package 2>&1 | Out-String
        if ($packageCheck -notmatch "Name:\s+$package") {
            $missingPackages += $package
        }
    } catch {
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host "Installing missing packages: $($missingPackages -join ', ')" -ForegroundColor Yellow
    foreach ($package in $missingPackages) {
        & pip install $package
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to install $package" -ForegroundColor Red
            exit 1
        }
    }
}

# Set default port if not set
if (-not $env:PORT) {
    $env:PORT = "8000"
}

# Start the server
Write-Host "Starting server on http://127.0.0.1:$env:PORT" -ForegroundColor Green
Write-Host "API Documentation: http://127.0.0.1:$env:PORT/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Use python -m uvicorn to ensure it runs from the virtual environment
# Use the venv's Python explicitly to ensure correct execution
$venvPython = "venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m uvicorn main:app --reload --host 127.0.0.1 --port $env:PORT
} else {
    # Fallback to python command (should work after venv activation)
    python -m uvicorn main:app --reload --host 127.0.0.1 --port $env:PORT
}

