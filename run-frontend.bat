@echo off
REM Starts the Next.js dashboard on http://localhost:3000
cd /d "%~dp0frontend"
if not exist node_modules (
    echo Dependencies are missing. Run setup.bat first.
    pause
    exit /b 1
)
if not exist .env.local copy .env.local.example .env.local >nul
echo Starting the dashboard on http://localhost:3000
echo Press Ctrl+C to stop.
call npm run dev
pause
