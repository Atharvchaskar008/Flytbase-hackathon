# TRACE - PostgreSQL Password Setup Script
Write-Host "Setting up PostgreSQL password for TRACE..." -ForegroundColor Green
Write-Host ""

# Prompt for password securely
$password = Read-Host "Enter your PostgreSQL 'postgres' user password" -AsSecureString
$plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($password))

# Update .env file
$envContent = Get-Content ".env"
$newEnvContent = $envContent -replace "DATABASE_URL=.*", "DATABASE_URL=postgresql://postgres:$plainPassword@localhost:5432/trace"
$newEnvContent | Set-Content ".env"

Write-Host "✅ Database URL updated in .env file" -ForegroundColor Green
Write-Host ""

# Test connection
Write-Host "Testing PostgreSQL connection..." -ForegroundColor Yellow
python check_postgres.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "🎉 PostgreSQL connection successful!" -ForegroundColor Green
} else {
    Write-Host "❌ Connection failed. Please check your password." -ForegroundColor Red
}