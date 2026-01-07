#!/bin/bash
# Start script for Route Optimization API (Bash)
# Usage: ./scripts/start.sh

set -e

echo "Starting Route Optimization API..."

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.11 or later."
    exit 1
fi

echo "Using Python: $($PYTHON_CMD --version)"

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Virtual environment not found. Creating one..."
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if uvicorn is installed
if ! pip show uvicorn &> /dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Set default port if not set
export PORT=${PORT:-8000}

# Start the server
echo "Starting server on http://127.0.0.1:$PORT"
echo "API Documentation: http://127.0.0.1:$PORT/docs"
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn main:app --reload --host 127.0.0.1 --port $PORT

