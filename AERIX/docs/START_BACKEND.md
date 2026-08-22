# TRACE Backend - Startup Guide

## Prerequisites

1. **PostgreSQL must be running**
2. **Database 'trace' must exist**
3. **Python 3.10+ with dependencies installed**

---

## Quick Start

### Step 1: Check PostgreSQL Connection

```powershell
python check_postgres.py
```

**Expected output:**
```
✓ Loaded .env from c:\Users\athar\OneDrive\Desktop\Trace\.env
✓ DATABASE_URL: postgresql://postgres:****@localhost:5432/trace
Testing PostgreSQL connection...
✓ Connected to PostgreSQL
  Version: PostgreSQL 14.x
  Tables in database: 12
✓ PostgreSQL is ready!
```

If this fails, follow the troubleshooting steps shown in the output.

---

### Step 2: Start Backend

**Method 1: Using uvicorn directly (recommended)**
```powershell
cd "c:\Users\athar\OneDrive\Desktop\Trace"
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Method 2: Using python module**
```powershell
cd "c:\Users\athar\OneDrive\Desktop\Trace"
python -m backend
```

---

## Expected Startup Output

When backend starts successfully, you should see:

```
✓ Loaded environment from: c:\Users\athar\OneDrive\Desktop\Trace\.env
✓ DATABASE_URL loaded: postgresql://postgres:****@localhost:5432/trace
✓ Upload directory: c:\Users\athar\OneDrive\Desktop\Trace\storage\uploads
✓ Video directory: c:\Users\athar\OneDrive\Desktop\Trace\storage\videos
✓ Log level: INFO
✓ SQLAlchemy engine created

============================================================
TRACE Backend Startup
============================================================

[1/5] Environment Validation
✓ Environment loaded
✓ Project root: c:\Users\athar\OneDrive\Desktop\Trace
✓ Debug mode: False

[2/5] Database Connection
→ Testing database connection...
✓ Connected to PostgreSQL
→ Creating database tables...
✓ Database tables initialized
✓ PostgreSQL connected and initialized

[3/5] Directory Setup
✓ Upload directory ready: c:\Users\athar\OneDrive\Desktop\Trace\storage\uploads
✓ Video directory ready: c:\Users\athar\OneDrive\Desktop\Trace\storage\videos
✓ Clips directory ready: c:\Users\athar\OneDrive\Desktop\Trace\storage\clips

[4/5] Static Files
✓ Clips mounted at /clips

[5/5] API Routes
✓ Upload API registered
✓ Timeline API registered
✓ Search API registered
✓ Clip API registered

============================================================
✓ TRACE Backend Started Successfully
============================================================

API Version: 0.1.0
API Documentation: http://localhost:8000/docs
Health Check: http://localhost:8000/health
Database Health: http://localhost:8000/health/db

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Common Issues & Solutions

### Issue 1: PostgreSQL Not Running

**Error:**
```
❌ PostgreSQL connection failed: connection refused
```

**Solution:**
```powershell
# Windows - Start PostgreSQL service
services.msc
# Find "PostgreSQL" service and start it

# Or via command line
net start postgresql-x64-14
```

---

### Issue 2: Database Does Not Exist

**Error:**
```
❌ PostgreSQL connection failed: database "trace" does not exist
```

**Solution:**
```powershell
# Connect to PostgreSQL
psql -U postgres

# Create database (in psql prompt)
CREATE DATABASE trace;
\q
```

---

### Issue 3: Wrong Password

**Error:**
```
❌ PostgreSQL connection failed: password authentication failed
```

**Solution:**
Edit `.env` file and update DATABASE_URL:
```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/trace
```

If PostgreSQL has no password:
```env
DATABASE_URL=postgresql://postgres@localhost:5432/trace
```

---

### Issue 4: MODULE_NOT_FOUND Error

**Error:**
```
ModuleNotFoundError: No module named 'backend'
```

**Solution:**
Make sure you're running from the project root:
```powershell
cd "c:\Users\athar\OneDrive\Desktop\Trace"
uvicorn backend.main:app --reload
```

Not from inside the backend folder!

---

### Issue 5: Dependencies Missing

**Error:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**
```powershell
cd backend
pip install -r requirements.txt
```

---

## Verify Backend is Running

### 1. Health Check
```powershell
curl http://localhost:8000/health
```
Expected: `{"status":"ok","version":"0.1.0"}`

### 2. Database Health
```powershell
curl http://localhost:8000/health/db
```
Expected: `{"status":"ok","database":"Connected to PostgreSQL"}`

### 3. API Documentation
Open browser: http://localhost:8000/docs

---

## Environment Variables Reference

Required variables in `.env`:

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/trace

# Optional
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
DEBUG=false
```

---

## Stopping the Backend

Press `Ctrl+C` in the terminal where backend is running.

Expected output:
```
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process
```

---

## Summary of Fixes

The following issues were fixed:

1. ✓ Environment loading from project root
2. ✓ DATABASE_URL validation with masked logging
3. ✓ PostgreSQL connection with clear error messages
4. ✓ Directory creation on startup
5. ✓ Comprehensive startup validation
6. ✓ Model imports before table creation
7. ✓ Readable error messages (no long tracebacks)
8. ✓ Support for running as module or with uvicorn

All fixes maintain the existing architecture - no models, APIs, services, or repositories were changed.
