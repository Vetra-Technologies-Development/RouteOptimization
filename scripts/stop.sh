#!/bin/bash
# Stop script for Route Optimization API (Bash)
# Usage: ./scripts/stop.sh

set -e

echo "Stopping Route Optimization API..."

# Find and kill uvicorn processes
PIDS=$(ps aux | grep "[u]vicorn main:app" | awk '{print $2}')

if [ -z "$PIDS" ]; then
    # Alternative: Find by port (default 8000)
    PORT=${PORT:-8000}
    echo "Checking for processes on port $PORT..."
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    
    if [ -n "$PID" ]; then
        echo "Stopping process on port $PORT (PID: $PID)..."
        kill -9 $PID
        echo "Server stopped."
    else
        echo "No server process found running."
    fi
else
    for PID in $PIDS; do
        echo "Stopping process $PID..."
        kill -9 $PID 2>/dev/null || true
    done
    echo "Server stopped."
fi

