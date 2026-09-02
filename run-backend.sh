#!/usr/bin/env bash
# Starts the FastAPI backend on http://localhost:8000
set -e
cd "$(dirname "$0")/backend"
if [ ! -x .venv/bin/python ]; then
    echo "The virtual environment is missing. Run ./setup.sh first."
    exit 1
fi
echo "Starting the backend on http://localhost:8000  (API docs: /docs)"
echo "Press Ctrl+C to stop."
exec .venv/bin/python -m uvicorn app.main:app --reload --port 8000
