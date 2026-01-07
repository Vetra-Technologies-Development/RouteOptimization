# Scripts

This folder contains scripts to manage the Route Optimization API locally.

## Available Scripts

### Windows (PowerShell)

- **`start.ps1`** - Start the API server
- **`stop.ps1`** - Stop the API server
- **`restart.ps1`** - Restart the API server

### Linux/Mac (Bash)

- **`start.sh`** - Start the API server
- **`stop.sh`** - Stop the API server
- **`restart.sh`** - Restart the API server

## Usage

### Windows

```powershell
# Start the server
.\scripts\start.ps1

# Stop the server
.\scripts\stop.ps1

# Restart the server
.\scripts\restart.ps1
```

### Linux/Mac

```bash
# Make scripts executable (first time only)
chmod +x scripts/*.sh

# Start the server
./scripts/start.sh

# Stop the server
./scripts/stop.sh

# Restart the server
./scripts/restart.sh
```

## Features

- Automatically creates and activates virtual environment if it doesn't exist
- Installs dependencies automatically
- Uses port 8000 by default (or PORT environment variable)
- Server runs with auto-reload enabled for development
- API documentation available at http://127.0.0.1:8000/docs

## Environment Variables

- `PORT` - Port number to run the server on (default: 8000)
- Other environment variables can be set in `.env` file

## Notes

- The scripts will create a `venv` folder if it doesn't exist
- Dependencies are automatically installed from `requirements.txt`
- The server runs in development mode with auto-reload enabled
- Press `Ctrl+C` to stop the server when running `start.ps1` or `start.sh`

