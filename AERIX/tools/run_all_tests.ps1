# TRACE - Comprehensive Test Suite
# This script runs all tests and checks in one place

param(
    [switch]$Quick,
    [switch]$Database,
    [switch]$Backend,
    [switch]$All
)

Write-Host "============================================================" -ForegroundColor Green
Write-Host "TRACE - Comprehensive Test Suite" -ForegroundColor Green  
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

$ErrorCount = 0

function Test-PostgreSQL {
    Write-Host "[TEST 1] PostgreSQL Connection" -ForegroundColor Yellow
    try {
        $result = python check_postgres.py 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ PostgreSQL connection test passed" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ PostgreSQL connection test failed" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Could not run PostgreSQL test" -ForegroundColor Red
        return $false
    }
}

function Test-StartupConfiguration {
    Write-Host "[TEST 2] Backend Startup Configuration" -ForegroundColor Yellow
    try {
        $result = python test_startup.py 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Startup configuration test passed" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Startup configuration test failed" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Could not run startup configuration test" -ForegroundColor Red
        return $false
    }
}

function Test-DatabaseInitialization {
    Write-Host "[TEST 3] Database Initialization" -ForegroundColor Yellow
    try {
        # Check if tables exist or initialize them
        $result = python init_database.py 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Database initialization test passed" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Database initialization test failed" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Could not run database initialization test" -ForegroundColor Red
        return $false
    }
}

function Test-PythonDependencies {
    Write-Host "[TEST 4] Python Dependencies" -ForegroundColor Yellow
    try {
        Set-Location backend
        .\venv\Scripts\Activate.ps1
        
        # Test key packages
        $packages = @("fastapi", "sqlalchemy", "opencv-python", "ultralytics", "psycopg2")
        $allFound = $true
        
        foreach ($package in $packages) {
            $result = python -c "import $($package.Replace('-', '_')); print('✓ $package')" 2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "❌ Missing package: $package" -ForegroundColor Red
                $allFound = $false
            }
        }
        
        Set-Location ..
        
        if ($allFound) {
            Write-Host "✅ Python dependencies test passed" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Python dependencies test failed" -ForegroundColor Red
            return $false
        }
    } catch {
        Set-Location ..
        Write-Host "❌ Could not test Python dependencies" -ForegroundColor Red
        return $false
    }
}
}

function Test-FrontendDependencies {
    Write-Host "[TEST 5] Frontend Dependencies" -ForegroundColor Yellow
    try {
        if (Test-Path "frontend/node_modules") {
            Write-Host "✅ Frontend dependencies test passed (node_modules exists)" -ForegroundColor Green
            return $true
        } else {
            Write-Host "⚠️  Frontend dependencies not installed (run npm install)" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "❌ Could not test frontend dependencies" -ForegroundColor Red
        return $false
    }
}

function Test-FFmpeg {
    Write-Host "[TEST 6] FFmpeg Installation" -ForegroundColor Yellow
    try {
        $result = ffmpeg -version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ FFmpeg test passed" -ForegroundColor Green
            return $true
        } else {
            Write-Host "⚠️  FFmpeg not found in PATH" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "⚠️  FFmpeg not installed or not in PATH" -ForegroundColor Yellow
        return $false
    }
}

function Test-BackendAPI {
    Write-Host "[TEST 7] Backend API (Optional)" -ForegroundColor Yellow
    try {
        if (Test-Path "test_backend.py") {
            Write-Host "ℹ️  Backend API test available (run 'python test_backend.py' when server is running)" -ForegroundColor Cyan
            return $true
        } else {
            Write-Host "ℹ️  Backend API test not found" -ForegroundColor Cyan
            return $true
        }
    } catch {
        Write-Host "ℹ️  Could not check for backend API test" -ForegroundColor Cyan
        return $true
    }
}

function Test-DirectoryStructure {
    Write-Host "[TEST 8] Directory Structure" -ForegroundColor Yellow
    try {
        $requiredDirs = @(
            "backend",
            "backend/api", 
            "backend/core",
            "database",
            "database/models",
            "frontend",
            "frontend/src",
            "ml_pipeline",
            "services"
        )
        
        $allFound = $true
        foreach ($dir in $requiredDirs) {
            if (-not (Test-Path $dir)) {
                Write-Host "❌ Missing directory: $dir" -ForegroundColor Red
                $allFound = $false
            }
        }
        
        if ($allFound) {
            Write-Host "✅ Directory structure test passed" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Directory structure test failed" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Could not test directory structure" -ForegroundColor Red
        return $false
    }
}

# Main test execution
Write-Host "Running TRACE test suite..." -ForegroundColor Cyan
Write-Host "Use parameters: -Quick (essential tests only), -Database (DB tests), -Backend (backend tests), -All (everything)" -ForegroundColor Gray
Write-Host ""

# Always run essential tests
$tests = @()

if ($Quick -or $All -or (-not $Database -and -not $Backend)) {
    $tests += @(
        { Test-DirectoryStructure },
        { Test-PostgreSQL },
        { Test-StartupConfiguration }
    )
}

if ($Database -or $All) {
    $tests += @(
        { Test-PostgreSQL },
        { Test-DatabaseInitialization }
    )
}

if ($Backend -or $All) {
    $tests += @(
        { Test-PythonDependencies },
        { Test-StartupConfiguration },
        { Test-BackendAPI }
    )
}

if ($All) {
    $tests += @(
        { Test-DirectoryStructure },
        { Test-PostgreSQL },
        { Test-StartupConfiguration },
        { Test-DatabaseInitialization },
        { Test-PythonDependencies },
        { Test-FrontendDependencies },
        { Test-FFmpeg },
        { Test-BackendAPI }
    )
}

# Remove duplicates by converting to unique function names
$uniqueTests = $tests | Select-Object -Unique

# Run all tests
$passedTests = 0
$totalTests = $uniqueTests.Count

foreach ($test in $uniqueTests) {
    $result = & $test
    if ($result) {
        $passedTests++
    } else {
        $ErrorCount++
    }
    Write-Host ""
}

# Summary
Write-Host "============================================================" -ForegroundColor Green
Write-Host "TEST SUMMARY" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Total Tests: $totalTests" -ForegroundColor Cyan
Write-Host "Passed: $passedTests" -ForegroundColor Green
Write-Host "Failed: $($totalTests - $passedTests)" -ForegroundColor Red
Write-Host ""

if ($ErrorCount -eq 0) {
    Write-Host "🎉 All tests passed! TRACE is ready to run." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. If PostgreSQL/FFmpeg tests failed, install those dependencies" -ForegroundColor Gray
    Write-Host "2. Run './start.ps1' to start both backend and frontend" -ForegroundColor Gray
    Write-Host "3. Open http://localhost:3000 in your browser" -ForegroundColor Gray
} else {
    Write-Host "⚠️  Some tests failed. Check the issues above and:" -ForegroundColor Yellow
    Write-Host "- Install missing dependencies (PostgreSQL, FFmpeg)" -ForegroundColor Gray
    Write-Host "- Run npm install in frontend directory" -ForegroundColor Gray
    Write-Host "- Check SETUP_COMPLETE.md for detailed instructions" -ForegroundColor Gray
}

Write-Host ""
Write-Host "For help: See README.md and SETUP_COMPLETE.md" -ForegroundColor Cyan