@echo off
REM Starts the FastAPI backend on http://localhost:8000
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe (
    echo The virtual environment is missing. Run setup.bat first.
    pause
    exit /b 1
)
echo Starting the backend on http://localhost:8000  (API docs: /docs)
echo Press Ctrl+C to stop.
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
pause
