@echo off
REM ===================================================================
REM  First-time setup - Windows
REM  Creates the Python virtual environment, installs all dependencies
REM  and loads the sample data. Run this once.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo === Checking Python ===
set "PY=python"
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"
%PY% --version
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python was not found.
    echo Install Python 3.12 or 3.13 from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

echo.
echo === Checking Node.js ===
call node --version
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Node.js was not found.
    echo Install Node.js 20 or newer from https://nodejs.org/
    pause
    exit /b 1
)

echo.
echo === Creating the Python virtual environment ===
cd /d "%~dp0backend"
if exist .venv\pyvenv.cfg (
    echo Virtual environment already exists, reusing it.
) else (
    %PY% -m venv .venv
    if %errorlevel% neq 0 goto :failed
)

echo.
echo === Installing backend dependencies (this takes a few minutes) ===
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if %errorlevel% neq 0 goto :failed

echo.
echo === Loading the sample data and running a first schedule ===
.venv\Scripts\python.exe -m scripts.seed --reset
if %errorlevel% neq 0 goto :failed

echo.
echo === Installing frontend dependencies ===
cd /d "%~dp0frontend"
if not exist .env.local copy .env.local.example .env.local >nul
call npm install
if %errorlevel% neq 0 goto :failed

echo.
echo ===================================================================
echo  Setup finished.
echo.
echo  Now start the two servers - each in its own window:
echo      run-backend.bat
echo      run-frontend.bat
echo.
echo  Then open http://localhost:3000
echo      email:    admin@example.com
echo      password: admin123
echo ===================================================================
pause
exit /b 0

:failed
echo.
echo Setup failed. See the error above, and check the Troubleshooting
echo section in torun.txt.
pause
exit /b 1
