# TRACE - Setup and Run Instructions

Complete guide to set up and run the TRACE video surveillance system locally.

## Prerequisites

### Required Software

1. **Python 3.10+**
   - Download from: https://www.python.org/downloads/

2. **PostgreSQL 14+**
   - Download from: https://www.postgresql.org/download/
   - During installation, remember the password for user `postgres`

3. **FFmpeg**
   - Download from: https://ffmpeg.org/download.html
   - Windows: Download build, extract, and add to PATH
   - Verify: `ffmpeg -version`

4. **Node.js 18+ and npm** (for frontend)
   - Download from: https://nodejs.org/

### Optional (for production)
- Redis (for caching and real-time features)

---

## Backend Setup

### 1. Create PostgreSQL Database

```powershell
# Connect to PostgreSQL
psql -U postgres

# In psql prompt:
CREATE DATABASE trace;
\q
```

### 2. Configure Environment

Edit `backend/.env`:
```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/trace
```

Replace `YOUR_PASSWORD` with your PostgreSQL password.

### 3. Install Python Dependencies

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Note**: Installing dependencies may take 5-10 minutes (torch, transformers are large).

### 4. Initialize Database

```powershell
# Still in backend folder with venv activated
cd ..
python -c "from database.database import init_db; init_db()"
```

This creates all tables and seed data (default camera).

### 5. Run Backend Server

```powershell
# From project root, with backend venv activated
cd backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `http://localhost:8000`

**Verify it's running:**
- Open browser: `http://localhost:8000/health`
- Should see: `{"status": "ok"}`

---

## Frontend Setup

### 1. Install Dependencies

```powershell
# Open a NEW terminal window
cd frontend
npm install
```

### 2. Configure API URL

Create `frontend/.env`:
```env
REACT_APP_API_URL=http://localhost:8000
```

### 3. Run Frontend Server

```powershell
# In frontend folder
npm start
```

Frontend will open automatically at: `http://localhost:3000`

---

## Testing the Complete Pipeline

### Step 1: Upload a Video

1. Open `http://localhost:3000` in your browser
2. Go to "1. Upload Video" section
3. Click "Choose File" and select a video (MP4, AVI, MOV, etc.)
4. Click "Upload"
5. **Copy the `video_id`** from the response (you'll need it)

Example response:
```json
{
  "id": "a1b2c3d4-1234-5678-90ab-cdef12345678",
  "video_id": "a1b2c3d4-1234-5678-90ab-cdef12345678",
  "filename": "test.mp4",
  "status": "uploaded"
}
```

### Step 2: Process the Video

1. Paste the `video_id` into "2. Process Video" section
2. Click "Process"
3. Wait for processing to complete (may take 1-2 minutes for a short video)

**What happens:**
- Video → Frame Sampling (1 FPS)
- YOLO Detection (person detection)
- Object Tracking (assigns IDs)
- Event Generation (track_started, track_updated, track_ended)
- Database Storage

### Step 3: View Videos List

1. Click "Get Videos" in "3. List Videos"
2. You'll see your uploaded video with status `processed`
3. Click any "Load Events" or "Load Timeline" button

### Step 4: View Timeline (Phase 9)

Timeline shows all events chronologically:
```json
[
  {
    "time": "00:00:15",
    "track": 1,
    "event": "track_started",
    "confidence": 0.95,
    "description": "New track started for person"
  },
  {
    "time": "00:00:18",
    "track": 1,
    "event": "track_updated",
    "confidence": 0.94,
    "description": "Person movement tracked"
  }
]
```

### Step 5: View Events

Raw events with full metadata including bounding boxes and frame numbers.

### Step 6: Image Search (Phase 10)

1. Go to "5. Image Search"
2. Upload an image of a person
3. Click "Search Image"
4. See matching tracks with similarity scores

**Note:** For demo mode, this generates mock results. Enable real YOLO to get actual matches.

### Step 7: Text Search (Phase 11)

1. Go to "4. Search"
2. Enter a query like "red cap" or "person in blue shirt"
3. Click "Search"
4. See matching frames

**Note:** Uses CLIP for semantic search. In demo mode, generates mock results.

### Step 8: Clip Retrieval (Phase 12)

1. Copy an `event_id` from the Events display
2. Paste into "6. Clip Retrieval"
3. Click "Get Clip"
4. Video player will show a 30-second clip (±15s from event)

---

## API Endpoints Reference

### Video Management
- `POST /upload/video` - Upload video file
- `POST /upload/process/{video_id}` - Process video through ML pipeline
- `GET /upload/videos` - List all videos

### Timeline & Events (Phase 9)
- `GET /videos/{video_id}/timeline` - Get timeline of events
- `GET /videos/{video_id}/events` - Get raw events
- `GET /videos/{video_id}/tracks` - Get all tracks

### Search (Phase 10 & 11)
- `POST /search/image` - Image-based person search
- `POST /search/text` - Natural language frame search
- `GET /search/suggestions` - Get search query examples
- `GET /search/status` - Get search system status

### Clips (Phase 12)
- `GET /clip/{event_id}` - Get clip for event
- `GET /clip/{event_id}/download` - Download clip file

### Health Checks
- `GET /health` - API health
- `GET /health/db` - Database connection check

---

## Troubleshooting

### Backend won't start

**Error: `Cannot connect to database`**
- Check PostgreSQL is running: `pg_ctl status`
- Verify credentials in `backend/.env`
- Test connection: `psql -U postgres -d trace`

**Error: `FFmpeg not found`**
- Install FFmpeg and add to PATH
- Verify: `ffmpeg -version`

**Error: `Module not found`**
- Ensure venv is activated
- Reinstall: `pip install -r requirements.txt`

### Frontend won't start

**Error: `Cannot connect to backend`**
- Check backend is running on port 8000
- Verify `REACT_APP_API_URL` in `frontend/.env`

**Error: `npm install fails`**
- Try: `npm cache clean --force`
- Delete `node_modules` and `package-lock.json`, retry

### Video Processing Issues

**Processing hangs or fails**
- Check video format (MP4 works best)
- Check file size (under 500MB)
- Look at backend console for errors

**No detections in results**
- Demo mode uses mock YOLO (generates fake detections)
- For real detection, set `use_real_yolo=True` in pipeline

---

## Demo Mode vs Production Mode

### Demo Mode (Default)
- Uses mock YOLO detector (fake person detections)
- Uses mock Re-ID model (random embeddings)
- Uses mock CLIP model (random similarities)
- **Advantage**: Works without downloading large models
- **Good for**: Testing API flow, UI development

### Production Mode
- Download real models:
  - YOLOv8: `yolo task=detect mode=predict model=yolov8n.pt`
  - CLIP: Automatically downloads from Hugging Face
- Enable in code:
  - `YOLODetector(use_real_yolo=True)`
  - `PersonReID(use_mock=False)`
  - `CLIPSearch(use_mock=False)`

---

## File Structure

```
Trace/
├── backend/              # FastAPI backend
│   ├── api/             # API endpoints
│   ├── core/            # Config, logging
│   ├── main.py          # FastAPI app
│   └── requirements.txt
├── frontend/            # React frontend
│   └── src/
│       ├── components/  # React components
│       ├── pages/       # Pages
│       └── services/    # API services
├── database/            # Database models & migrations
│   ├── models/         # SQLAlchemy models
│   └── repository/     # Data access layer
├── ml_pipeline/         # ML processing pipeline
│   ├── detection/      # YOLO detector
│   ├── tracking/       # Object tracking
│   ├── reid/           # Person Re-ID
│   ├── search/         # CLIP search
│   └── pipeline.py     # Main orchestrator
├── services/            # Business logic
│   ├── video_service.py
│   └── clip_service.py
└── storage/             # File storage
    ├── videos/         # Uploaded videos
    └── clips/          # Extracted clips
```

---

## Quick Start (TL;DR)

```powershell
# Terminal 1: Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
python -c "from database.database import init_db; init_db()"
cd backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm start

# Open browser: http://localhost:3000
# Upload video → Process → View timeline → Search → Get clips
```

---

## Support

If you encounter issues:
1. Check backend logs in Terminal 1
2. Check frontend console (F12 in browser)
3. Verify all prerequisites are installed
4. Check database connection

---

## Next Steps

After successful testing:
1. Enable production models (YOLO, CLIP)
2. Add more cameras
3. Implement zones
4. Add user authentication
5. Deploy to production server

---

**System Status:**
- ✅ Phase 9: Timeline API
- ✅ Phase 10: Image Search
- ✅ Phase 11: Text Search
- ✅ Phase 12: Clip Service

All backend APIs are functional and ready for testing!
