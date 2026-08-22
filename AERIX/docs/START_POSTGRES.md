# Start PostgreSQL - Complete Guide

## Current Status

**PostgreSQL is NOT running.** The backend tests pass but cannot connect to the database.

---

## Option 1: Start System PostgreSQL (Recommended)

### Check if PostgreSQL is Installed

```powershell
# Check if PostgreSQL is installed
Get-Service -Name "postgresql*"
```

If you see a service listed, PostgreSQL is installed.

### Start PostgreSQL Service

```powershell
# Start PostgreSQL service (run as Administrator)
Start-Service postgresql-x64-14
# Or whatever version you have

# Or use services.msc
services.msc
# Find PostgreSQL service → Right-click → Start
```

### Verify PostgreSQL is Running

```powershell
# Check service status
Get-Service -Name "postgresql*"

# Or test connection
python check_postgres.py
```

---

## Option 2: Install PostgreSQL (If Not Installed)

### Download PostgreSQL

1. Go to: https://www.postgresql.org/download/windows/
2. Download the installer (PostgreSQL 14 or later)
3. Run installer with these settings:
   - **Port:** 5432 (default)
   - **Superuser:** postgres
   - **Password:** Leave blank or remember it
   - Install in default location

### After Installation

```powershell
# Start PostgreSQL
Start-Service postgresql-x64-14

# Create database
psql -U postgres
CREATE DATABASE trace;
\q
```

---

## Option 3: Use Docker (Alternative)

If you have Docker Desktop installed:

```powershell
# Start PostgreSQL in Docker
docker run -d `
  --name trace-postgres `
  -e POSTGRES_DB=trace `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_HOST_AUTH_METHOD=trust `
  -p 5432:5432 `
  postgres:14-alpine

# Check if running
docker ps

# Test connection
python check_postgres.py
```

### Stop Docker PostgreSQL

```powershell
docker stop trace-postgres
docker rm trace-postgres
```

---

## Option 4: Embedded PostgreSQL (Project-specific)

The `.postgres` folder suggests an embedded PostgreSQL, but it appears incomplete.

### Check if PostgreSQL Binary Exists

```powershell
# Look for postgres.exe
Get-ChildItem -Path ".postgres" -Recurse -Filter "postgres.exe"
```

If found, you can start it with:

```powershell
# Navigate to bin directory
cd .postgres\pgsql\bin

# Initialize database (first time only)
.\initdb.exe -D ..\..\data -U postgres -A trust

# Start PostgreSQL
.\pg_ctl.exe -D ..\..\data -l ..\..\pg.log start

# Create database
.\createdb.exe -U postgres trace
```

---

## Verify PostgreSQL is Working

After starting PostgreSQL using any method:

```powershell
# Test 1: Check if service is listening on port 5432
Test-NetConnection -ComputerName localhost -Port 5432

# Test 2: Run PostgreSQL check script
python check_postgres.py

# Expected output:
# ✓ Connected to PostgreSQL
# ✓ PostgreSQL is ready!
```

---

## Create Database 'trace'

Once PostgreSQL is running:

```powershell
# Method 1: Using psql
psql -U postgres
CREATE DATABASE trace;
\q

# Method 2: Using createdb
createdb -U postgres trace

# Method 3: Using our initialization script
python init_database.py
```

---

## Update .env (If Needed)

If you set a password during PostgreSQL installation:

Edit `C:\Users\athar\OneDrive\Desktop\Trace\.env`:

```env
# No password (default)
DATABASE_URL=postgresql://postgres@localhost:5432/trace

# With password
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/trace
```

---

## Quick Troubleshooting

### Error: "Connection refused"
**Cause:** PostgreSQL is not running  
**Fix:** Start PostgreSQL service (see Option 1)

### Error: "database 'trace' does not exist"
**Cause:** Database not created  
**Fix:** Run `CREATE DATABASE trace;` in psql

### Error: "password authentication failed"
**Cause:** Wrong password in .env  
**Fix:** Update DATABASE_URL in .env with correct password

### Error: "port 5432 already in use"
**Cause:** Another PostgreSQL instance is running  
**Fix:** Stop other instance or use different port

---

## Recommended Workflow

1. **Check if PostgreSQL is installed:**
   ```powershell
   Get-Service -Name "postgresql*"
   ```

2. **If installed, start it:**
   ```powershell
   Start-Service postgresql-x64-14
   ```

3. **If not installed, install PostgreSQL:**
   - Download from postgresql.org
   - Install with default settings
   - Remember password (or leave blank)

4. **Create database:**
   ```powershell
   psql -U postgres
   CREATE DATABASE trace;
   \q
   ```

5. **Verify connection:**
   ```powershell
   python check_postgres.py
   ```

6. **Initialize tables:**
   ```powershell
   python init_database.py
   ```

7. **Start backend:**
   ```powershell
   uvicorn backend.main:app --reload
   ```

---

## Current Test Results

```powershell
# Test 1: Configuration
python test_startup.py
# ✓ All startup tests passed!

# Test 2: PostgreSQL
python check_postgres.py
# ❌ PostgreSQL connection failed - CONNECTION REFUSED

# Test 3: Initialize database
python init_database.py
# ❌ Will fail because PostgreSQL is not running
```

**Next step:** Start PostgreSQL using one of the options above.

---

## Auto-Start PostgreSQL (Optional)

To make PostgreSQL start automatically on Windows boot:

```powershell
# Set service to start automatically
Set-Service -Name "postgresql-x64-14" -StartupType Automatic

# Or use services.msc
services.msc
# Find PostgreSQL → Properties → Startup type → Automatic
```

---

## Summary

**Current Issue:** PostgreSQL is not running on localhost:5432

**Solutions (pick one):**
1. ✅ Start system PostgreSQL service (fastest)
2. ✅ Install PostgreSQL from postgresql.org (recommended)
3. ✅ Use Docker PostgreSQL (if Docker available)
4. ⚠️  Use embedded .postgres (incomplete setup)

**After PostgreSQL starts:**
- Create database 'trace'
- Run `python check_postgres.py` to verify
- Run `python init_database.py` to create tables
- Start backend with `uvicorn backend.main:app --reload`
