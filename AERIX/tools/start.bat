@echo off
REM TRACE - Quick Start Batch Script

echo ============================================================
echo TRACE Video Analytics Platform - Quick Start
echo ============================================================
echo.

echo [1/4] Checking PostgreSQL connection...
python check_postgres.py
if %ERRORLEVEL% neq 0 (
    echo ❌ PostgreSQL connection failed
    echo Please install and start PostgreSQL first
    echo See SETUP_COMPLETE.md for instructions
    pause
    exit /b 1
)
echo ✅ PostgreSQL connected successfully

echo [2/4] Initializing database if needed...
python init_database.py
if %ERRORLEVEL% neq 0 (
    echo ❌ Database initialization failed
    pause
    exit /b 1
)
echo ✅ Database ready

echo [3/4] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo ⚠️ Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
    if %ERRORLEVEL% neq 0 (
        echo ❌ Frontend dependencies installation failed
        pause
        exit /b 1
    )
)
echo ✅ Frontend dependencies ready

echo [4/4] Starting application...
echo.
echo ============================================================
echo Starting TRACE Application
echo ============================================================
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo Starting backend server...
start "TRACE Backend" /D "%cd%\backend" cmd /k "call venv\Scripts\activate.bat && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak > nul

echo Starting frontend server...
start "TRACE Frontend" /D "%cd%\frontend" cmd /k "npm start"

echo.
echo ✅ Both servers started in separate windows
echo ✅ Frontend will automatically open in your browser
echo.
echo To stop: Close both command windows or press Ctrl+C in each
echo.
echo Happy coding! 🚀
pause