# TRACE - Simple Test Script
Write-Host "TRACE - Quick System Test" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green
Write-Host ""

$tests = 0
$passed = 0

# Test 1: PostgreSQL
Write-Host "[1/5] Testing PostgreSQL..." -NoNewline
$tests++
try {
    python check_postgres.py >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅" -ForegroundColor Green
        $passed++
    } else {
        Write-Host " ❌" -ForegroundColor Red
    }
} catch {
    Write-Host " ❌" -ForegroundColor Red
}

# Test 2: Backend Config
Write-Host "[2/5] Testing backend config..." -NoNewline
$tests++
try {
    python test_startup.py >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅" -ForegroundColor Green
        $passed++
    } else {
        Write-Host " ❌" -ForegroundColor Red
    }
} catch {
    Write-Host " ❌" -ForegroundColor Red
}

# Test 3: Python packages
Write-Host "[3/5] Testing Python packages..." -NoNewline
$tests++
try {
    Set-Location backend
    .\venv\Scripts\Activate.ps1 >$null 2>&1
    python -c "import fastapi, sqlalchemy; print('OK')" >$null 2>&1
    Set-Location ..
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅" -ForegroundColor Green
        $passed++
    } else {
        Write-Host " ❌" -ForegroundColor Red
    }
} catch {
    Set-Location ..
    Write-Host " ❌" -ForegroundColor Red
}

# Test 4: Frontend deps
Write-Host "[4/5] Testing frontend deps..." -NoNewline
$tests++
if (Test-Path "frontend/node_modules") {
    Write-Host " ✅" -ForegroundColor Green
    $passed++
} else {
    Write-Host " ⚠️" -ForegroundColor Yellow
}

# Test 5: FFmpeg
Write-Host "[5/5] Testing FFmpeg..." -NoNewline
$tests++
try {
    ffmpeg -version >$null 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " ✅" -ForegroundColor Green
        $passed++
    } else {
        Write-Host " ⚠️" -ForegroundColor Yellow
    }
} catch {
    Write-Host " ⚠️" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Results: $passed/$tests tests passed" -ForegroundColor Cyan

if ($passed -ge 3) {
    Write-Host "🎉 System is ready! Run .\start.ps1 to begin" -ForegroundColor Green
} else {
    Write-Host "⚠️  Install missing dependencies. See SETUP_COMPLETE.md" -ForegroundColor Yellow
}