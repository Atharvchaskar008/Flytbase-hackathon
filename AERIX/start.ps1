# TRACE - Quick Start Script
# Run this script to start the application after dependencies are installed

Write-Host "============================================================" -ForegroundColor Green
Write-Host "TRACE Video Analytics Platform - Quick Start" -ForegroundColor Green  
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# Check if PostgreSQL is running
Write-Host "[1/4] Checking PostgreSQL connection..." -ForegroundColor Yellow
try {
    $result = python tools\check_postgres.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ PostgreSQL connected successfully" -ForegroundColor Green
    } else {
        Write-Host "❌ PostgreSQL connection failed" -ForegroundColor Red
        Write-Host "Please install and start PostgreSQL first" -ForegroundColor Red
        Write-Host "See docs\SETUP_COMPLETE.md for instructions" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Could not test PostgreSQL connection" -ForegroundColor Red
    exit 1
}

# Check if database is initialized
Write-Host "[2/4] Checking database initialization..." -ForegroundColor Yellow
try {
    # Test if we can connect and if tables exist
    Set-Location backend
    .\venv\Scripts\Activate.ps1
    $result = python -c "
from database.database import engine
from sqlalchemy import text
try:
    with engine.connect() as conn:
        conn.execute(text('SELECT 1 FROM videos LIMIT 1'))
    print('Tables exist')
except:
    print('Tables missing')
" 2>$null
    Set-Location ..
    
    if ($result -eq "Tables exist") {
        Write-Host "✅ Database tables exist" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Database tables not found, initializing..." -ForegroundColor Yellow
        python tools\init_database.py
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Database initialized successfully" -ForegroundColor Green
        } else {
            Write-Host "❌ Database initialization failed" -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "⚠️  Testing database, will initialize if needed..." -ForegroundColor Yellow
    python tools\init_database.py
}

# Check frontend dependencies
Write-Host "[3/4] Checking frontend dependencies..." -ForegroundColor Yellow
if (Test-Path "frontend/node_modules") {
    Write-Host "✅ Frontend dependencies installed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location frontend
    npm install
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Frontend dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "❌ Frontend dependency installation failed" -ForegroundColor Red
        Set-Location ..
        exit 1
    }
    Set-Location ..
}

Write-Host "[4/4] Starting application..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Starting TRACE Application" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend will start at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend will open at: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C in both terminals to stop the servers" -ForegroundColor Yellow
Write-Host ""

# Start backend in new terminal
Write-Host "Starting backend server..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$pwd\backend'; .\venv\Scripts\Activate.ps1; Write-Host 'Backend Starting...' -ForegroundColor Green; uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

# Wait a moment
Start-Sleep -Seconds 3

# Start frontend in new terminal
Write-Host "Starting frontend server..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$pwd\frontend'; Write-Host 'Frontend Starting...' -ForegroundColor Green; npm start"

Write-Host ""
Write-Host "✅ Both servers started in separate terminals" -ForegroundColor Green
Write-Host "✅ Frontend will automatically open in your browser" -ForegroundColor Green
Write-Host ""
Write-Host "To stop: Close both terminal windows or press Ctrl+C in each" -ForegroundColor Yellow
Write-Host ""
Write-Host "Happy coding! 🚀" -ForegroundColor Green