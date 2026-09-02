#!/usr/bin/env bash
# ===================================================================
#  First-time setup - macOS / Linux
#  Creates the Python virtual environment, installs all dependencies
#  and loads the sample data. Run this once.
# ===================================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo
echo "=== Checking Python ==="
PY=""
for candidate in python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        version="$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
        case "$version" in
            3.10|3.11|3.12|3.13) PY="$candidate"; break ;;
        esac
    fi
done
if [ -z "$PY" ]; then
    echo "ERROR: No suitable Python found. Install Python 3.12 or 3.13."
    echo "       (Python 3.14 is not supported yet - pandas/numpy have no wheels for it.)"
    exit 1
fi
echo "Using $PY ($($PY --version))"

echo
echo "=== Checking Node.js ==="
if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: Node.js was not found. Install Node.js 20 or newer from https://nodejs.org/"
    exit 1
fi
node --version

echo
echo "=== Creating the Python virtual environment ==="
cd "$ROOT/backend"
if [ -f .venv/pyvenv.cfg ]; then
    echo "Virtual environment already exists, reusing it."
else
    "$PY" -m venv .venv
fi

echo
echo "=== Installing backend dependencies (this takes a few minutes) ==="
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt

echo
echo "=== Loading the sample data and running a first schedule ==="
.venv/bin/python -m scripts.seed --reset

echo
echo "=== Installing frontend dependencies ==="
cd "$ROOT/frontend"
[ -f .env.local ] || cp .env.local.example .env.local
npm install

echo
echo "==================================================================="
echo " Setup finished."
echo
echo " Now start the two servers - each in its own terminal:"
echo "     ./run-backend.sh"
echo "     ./run-frontend.sh"
echo
echo " Then open http://localhost:3000"
echo "     email:    admin@example.com"
echo "     password: admin123"
echo "==================================================================="
