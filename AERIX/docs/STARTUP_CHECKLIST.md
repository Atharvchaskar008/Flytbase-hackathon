# TRACE Backend - Startup Checklist

## ✓ Quick Startup Checklist

### Prerequisites (Do Once)

- [ ] PostgreSQL installed and running
- [ ] Python 3.10+ installed
- [ ] Database 'trace' created
- [ ] Backend dependencies installed (`pip install -r backend/requirements.txt`)

### Before Each Start

```powershell
# Navigate to project root
cd "c:\Users\athar\OneDrive\Desktop\Trace"

# Check PostgreSQL is working
python check_postgres.py
```

**Expected:** `✓ PostgreSQL is ready!`

### Start Backend

```powershell
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected:** `✓ TRACE Backend Started Successfully`

### Verify Running

Open browser: http://localhost:8000/docs

---

## 🚨 If Something Fails

### Error: "DATABASE_URL not found"

**Fix:** Check `.env` file exists in project root
```powershell
# View .env
Get-Content .env
```

Expected content:
```
DATABASE_URL=postgresql://postgres@localhost:5432/trace
```

---

### Error: "PostgreSQL connection failed"

**Fix 1:** Check if PostgreSQL is running
```powershell
# Windows
services.msc
# Look for PostgreSQL service, ensure it's "Running"
```

**Fix 2:** Check if database exists
```powershell
psql -U postgres -l
# Should show 'trace' in the list

# If not, create it:
psql -U postgres
CREATE DATABASE trace;
\q
```

**Fix 3:** Verify credentials
Edit `.env` and ensure username/password match your PostgreSQL setup

---

### Error: "ModuleNotFoundError: No module named 'backend'"

**Fix:** Run from project root, not from inside backend/
```powershell
# ❌ WRONG
cd backend
uvicorn main:app --reload

# ✓ CORRECT
cd "c:\Users\athar\OneDrive\Desktop\Trace"
uvicorn backend.main:app --reload
```

---

### Error: "Module not found: fastapi/sqlalchemy/etc"

**Fix:** Install dependencies
```powershell
cd backend
pip install -r requirements.txt
```

---

## 📋 Diagnostic Commands

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `python test_startup.py` | Test all imports | Before starting server |
| `python check_postgres.py` | Check database connection | When database errors occur |
| `python init_database.py` | Create database tables | First time setup |
| `curl http://localhost:8000/health` | Check if backend is running | After starting |
| `curl http://localhost:8000/health/db` | Check database connection | Database issues |

---

## 🎯 Expected Startup Sequence

1. **Environment Loading** ✓
2. **Database Connection** ✓
3. **Directory Setup** ✓
4. **Static Files** ✓
5. **API Routes** ✓

If any step fails, you'll see:
- ❌ Clear error message
- 📋 Troubleshooting steps
- 🚫 Backend stops (doesn't continue with broken config)

---

## 📞 Quick Help

| Issue | Command |
|-------|---------|
| Can't connect to PostgreSQL | `python check_postgres.py` |
| Import errors | `python test_startup.py` |
| Tables not created | `python init_database.py` |
| General help | Open `START_BACKEND.md` |
| Detailed fixes | Open `FIXES_APPLIED.md` |

---

## ✅ Success Indicators

When backend is ready:

```
✓ TRACE Backend Started Successfully
API Version: 0.1.0
API Documentation: http://localhost:8000/docs
Health Check: http://localhost:8000/health
Database Health: http://localhost:8000/health/db

INFO:     Uvicorn running on http://0.0.0.0:8000
```

You should be able to:
- Open http://localhost:8000/docs (API documentation)
- See all API endpoints listed
- Get `{"status":"ok"}` from /health

---

## 🔄 Full Reset (if needed)

If everything is broken:

```powershell
# 1. Stop backend (Ctrl+C)

# 2. Reset database
psql -U postgres
DROP DATABASE trace;
CREATE DATABASE trace;
\q

# 3. Check configuration
python test_startup.py

# 4. Check PostgreSQL
python check_postgres.py

# 5. Initialize database
python init_database.py

# 6. Start backend
uvicorn backend.main:app --reload
```

---

## 📚 Documentation Files

- `STARTUP_CHECKLIST.md` ← You are here (quick reference)
- `START_BACKEND.md` - Detailed startup guide
- `FIXES_APPLIED.md` - What was fixed and why
- `SETUP_AND_RUN.md` - Full system setup
- `QUICK_START.md` - Fast track guide

---

**Last Updated:** After startup fixes applied  
**Status:** All fixes tested and working
