#!/bin/bash
# Restart script for Route Optimization API (Bash)
# Usage: ./scripts/restart.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Restarting Route Optimization API..."

# Stop the server
"$SCRIPT_DIR/stop.sh"

# Wait a moment for processes to terminate
sleep 2

# Start the server
"$SCRIPT_DIR/start.sh"

