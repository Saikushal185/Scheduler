#!/usr/bin/env bash
# Starts the Next.js dashboard on http://localhost:3000
set -e
cd "$(dirname "$0")/frontend"
if [ ! -d node_modules ]; then
    echo "Dependencies are missing. Run ./setup.sh first."
    exit 1
fi
[ -f .env.local ] || cp .env.local.example .env.local
echo "Starting the dashboard on http://localhost:3000"
echo "Press Ctrl+C to stop."
exec npm run dev
