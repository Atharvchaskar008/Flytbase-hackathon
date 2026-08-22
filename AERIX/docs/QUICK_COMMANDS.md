# TRACE - Quick Command Reference

## 🚀 One-Command Startup

### Automated (Recommended)
```powershell
# PowerShell script (checks dependencies, starts both servers)
.\start.ps1

# Or batch file alternative
.\start.bat
```

## 🧪 Testing Commands

### Run All Tests
```powershell
# Complete test suite
.\run_all_tests.ps1 -All

# Quick essential tests only
.\run_all_tests.ps1 -Quick

# Database tests only
.\run_all_tests.ps1 -Database

# Backend tests only  
.\run_all_tests.ps1 -Backend
```

### Individual Tests
```powershell
# Test PostgreSQL connection
python check_postgres.py

# Test backend configuration
python test_startup.py

# Initialize database
python init_database.py

# Test backend APIs (when server is running)
python test_backend.py
```

## 🔧 Manual Startup

### Backend Server
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Server (New Terminal)
```powershell
cd frontend
npm start
```

### Alternative Backend Start
```powershell
# Using Python module
python -m backend
```

## 📋 Setup Commands

### First-Time Setup
```powershell
# Install frontend dependencies
cd frontend
npm install
cd ..

# Initialize database (after PostgreSQL is installed)
python init_database.py
```

### Dependency Checks
```powershell
# Check Python packages
cd backend
.\venv\Scripts\Activate.ps1
pip list
cd ..

# Check Node.js packages
cd frontend
npm list --depth=0
cd ..

# Check system dependencies
ffmpeg -version
psql --version
```

## 🔍 Diagnostic Commands

### Health Checks
```powershell
# API health (when server is running)
curl http://localhost:8000/health

# Database health (when server is running)  
curl http://localhost:8000/health/db

# Frontend status
curl http://localhost:3000
```

### File Structure Check
```powershell
# List important directories
Get-ChildItem -Directory backend,frontend,database,ml_pipeline,services
```

## 🛠️ Troubleshooting

### Reset Frontend
```powershell
cd frontend
Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
Remove-Item package-lock.json -ErrorAction SilentlyContinue
npm cache clean --force
npm install
cd ..
```

### Reset Python Environment (if needed)
```powershell
cd backend
Remove-Item -Recurse -Force venv -ErrorAction SilentlyContinue
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

### Check Processes
```powershell
# See if servers are running
Get-Process | Where-Object {$_.ProcessName -like "*node*" -or $_.ProcessName -like "*python*"}

# Kill servers if stuck
Stop-Process -Name "node" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
```

## 📊 Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Frontend Dashboard | http://localhost:3000 | Main web interface |
| Backend API | http://localhost:8000 | REST API endpoints |
| API Documentation | http://localhost:8000/docs | Interactive API docs |
| Health Check | http://localhost:8000/health | System status |
| Database Health | http://localhost:8000/health/db | Database status |

## ⚡ Quick Workflow

```powershell
# 1. Quick test everything
.\run_all_tests.ps1 -Quick

# 2. Start application
.\start.ps1

# 3. Open browser to http://localhost:3000

# 4. Upload and process a video

# 5. Explore features: timeline, search, clips
```

## 🎯 Production vs Demo Mode

### Current Mode: Demo (Safe for Testing)
- Mock AI models (no GPU required)
- Fast processing
- Predictable results

### Switch to Production Mode
Edit `backend/api/upload.py` line ~34:
```python
# Change:
process_video(video_id, db, sample_rate=30, use_real_yolo=False)

# To:
process_video(video_id, db, sample_rate=30, use_real_yolo=True)
```

## 📝 Notes

- **PowerShell**: Use `;` to chain commands, not `&&`
- **Paths**: Always use quotes around paths with spaces
- **Virtual Environment**: Must be activated before running Python commands
- **Ports**: Backend (8000), Frontend (3000) - make sure they're available
- **Dependencies**: PostgreSQL and FFmpeg are external requirements

## 🆘 Getting Help

1. **Check logs**: Backend shows detailed error messages
2. **Run diagnostics**: `.\run_all_tests.ps1 -All`
3. **Read docs**: `README.md`, `SETUP_COMPLETE.md`
4. **Check issues**: Look at console output in both terminal windows