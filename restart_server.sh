#!/bin/bash
# Script to restart the FastAPI server with proper environment setup

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Load environment variables
export $(cat .env | xargs)

# Kill any existing uvicorn processes
pkill -f "uvicorn main:app" || true

# Wait a moment
sleep 1

# Start the server
echo "Starting FastAPI server with Gemini AI enabled..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000

