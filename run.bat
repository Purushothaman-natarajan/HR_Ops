@echo off
title HR Ops Platform

echo ========================================
echo   Self-Healing HR Ops Platform
echo ========================================
echo.

:: Check for Python venv
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else (
    set PYTHON=python
)

:: Install frontend dependencies if missing
if not exist "frontend\node_modules" (
    echo [PRE] Installing frontend dependencies...
    cd /d frontend
    call npm install
    cd /d ..
)

:: Start backend in new window
echo [1/4] Starting backend on http://localhost:8000 ...
start "HR Ops Backend" cmd /c "%PYTHON% -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Give backend a moment to initialize
timeout /t 3 /nobreak >nul

:: Start frontend in new window
echo [2/4] Starting frontend on http://localhost:5173 ...
start "HR Ops Frontend" cmd /c "cd /d frontend && npm run dev"

:: Wait for backend to be healthy (up to 90 retries ~ 3 min for cold start)
echo [3/4] Waiting for backend to be ready (may take 90s on first boot)...
set RETRIES=0
:healthcheck
timeout /t 2 /nobreak >nul
set /a RETRIES+=1
if %RETRIES% gtr 90 (
    echo [WARN] Backend health check timed out after 3 minutes.
    echo        Check backend window for errors.
    goto skip_browser
)
>nul 2>&1 curl -s http://localhost:8000/health
if %errorlevel% neq 0 goto healthcheck

:: Extra wait for OpenAPI schema generation
timeout /t 3 /nobreak >nul

:: Open browser tabs
echo [4/4] Opening browser tabs...
start http://localhost:5173
timeout /t 1 /nobreak >nul
start http://localhost:8000/docs
timeout /t 1 /nobreak >nul
start http://localhost:8000/redoc

:skip_browser
echo.
echo ========================================
echo   HR Ops Platform is running!
echo ========================================
echo   Frontend:     http://localhost:5173
echo   Backend API:  http://localhost:8000
echo   Swagger Docs: http://localhost:8000/docs
echo   ReDoc Docs:   http://localhost:8000/redoc
echo ========================================
echo   Close this window to stop all services
echo ========================================

pause
