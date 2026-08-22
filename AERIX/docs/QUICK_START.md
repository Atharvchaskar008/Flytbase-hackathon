# TRACE - Quick Start Guide

## ✅ Phases 9-12 Complete!

All backend APIs and frontend are now implemented and ready to test.

---

## 🚀 Start Backend (Terminal 1)

```powershell
# Navigate to project
cd "c:\Users\athar\OneDrive\Desktop\Trace"

# Create & activate virtual environment (first time only)
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies (first time only)
pip install -r requirements.txt

# Initialize database (first time only)
cd ..
python -c "from database.database import init_db; init_db()"

# Start backend server
cd backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend running at:** http://localhost:8000

---

## 🎨 Start Frontend (Terminal 2)

```powershell
# Open NEW terminal
cd "c:\Users\athar\OneDrive\Desktop\Trace\frontend"

# Install dependencies (first time only)
npm install

# Start frontend
npm start
```

**Frontend opens at:** http://localhost:3000

---

## 🧪 Test Backend APIs (Optional - Terminal 3)

```powershell
# Open NEW terminal
cd "c:\Users\athar\OneDrive\Desktop\Trace"
python test_backend.py
```

---

## 📹 Test Complete Pipeline

### 1. **Upload Video**
   - Open http://localhost:3000
   - Section "1. Upload Video"
   - Choose a video file (MP4, AVI, MOV)
   - Click "Upload"
   - **Copy the `video_id`** from response

### 2. **Process Video**
   - Section "2. Process Video"
   - Paste the `video_id`
   - Click "Process"
   - Wait for processing (1-2 minutes)

### 3. **View Results**
   - Click "Get Videos" in section 3
   - Click "Load Events" or "Load Timeline"
   - See detected persons, tracks, and events!

### 4. **Timeline (Phase 9)**
   - Chronological list of all events
   - Shows: time, track ID, event type, confidence

### 5. **Image Search (Phase 10)**
   - Section "5. Image Search"
   - Upload a person image
   - Click "Search Image"
   - See matching tracks with similarity scores

### 6. **Text Search (Phase 11)**
   - Section "4. Search"
   - Type: "red cap" or "person in blue shirt"
   - Click "Search"
   - See matching frames

### 7. **Clip Retrieval (Phase 12)**
   - Copy an `event_id` from Events display
   - Section "6. Clip Retrieval"
   - Paste `event_id`
   - Click "Get Clip"
   - Video player shows 30-second clip!

---

## 📋 Available API Endpoints

### Video Management
- `POST /upload/video` - Upload video
- `POST /upload/process/{video_id}` - Process video
- `GET /upload/videos` - List all videos

### Timeline & Events (Phase 9) ✅
- `GET /videos/{video_id}/timeline` - Timeline view
- `GET /videos/{video_id}/events` - Raw events
- `GET /videos/{video_id}/tracks` - All tracks
- `GET /videos/{video_id}/timeline/summary` - Statistics

### Search (Phases 10 & 11) ✅
- `POST /search/image` - Image-based search
- `POST /search/text` - Natural language search
- `GET /search/suggestions` - Example queries
- `GET /search/status` - System status

### Clips (Phase 12) ✅
- `GET /clip/{event_id}` - Get video clip
- `GET /clip/{event_id}/download` - Download clip

### Health
- `GET /health` - API status
- `GET /health/db` - Database status

---

## 🎯 Demo vs Production

### Current Mode: DEMO
- Uses mock YOLO (fake detections)
- Uses mock Re-ID (random embeddings)
- Uses mock CLIP (random similarities)
- **Perfect for testing API flow!**

### To Enable Production:
Edit `backend/api/upload.py` line 34:
```python
# Change from:
process_video(video_id, db, sample_rate=30, use_real_yolo=False)

# To:
process_video(video_id, db, sample_rate=30, use_real_yolo=True)
```

---

## 🔧 Troubleshooting

### Backend won't start
```powershell
# Check PostgreSQL is running
psql -U postgres -d trace

# If database doesn't exist:
psql -U postgres
CREATE DATABASE trace;
\q
```

### Frontend won't start
```powershell
# Clear cache and reinstall
cd frontend
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm install
npm start
```

### FFmpeg not found
- Download: https://ffmpeg.org/download.html
- Add to PATH
- Verify: `ffmpeg -version`

---

## 📁 Project Structure

```
Trace/
├── backend/
│   ├── api/
│   │   ├── upload.py      ✅ Video upload & processing
│   │   ├── timeline.py    ✅ Phase 9: Timeline API
│   │   ├── search.py      ✅ Phase 10 & 11: Search
│   │   └── clip.py        ✅ Phase 12: Clip Service
│   └── main.py
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Dashboard/      ✅ Main testing UI
│       │   ├── Timeline/       ✅ Timeline display
│       │   ├── ImageSearch/    ✅ Image search
│       │   ├── VideoPlayer/    ✅ Clip playback
│       │   └── Chat/           ✅ Natural language
│       └── pages/
│           └── Landing/        ✅ Landing page
├── services/
│   └── clip_service.py    ✅ FFmpeg clip extraction
├── ml_pipeline/
│   └── pipeline.py        ✅ Complete ML pipeline
└── database/
    └── models/            ✅ All data models
```

---

## ✨ What's Working

✅ **Phase 9: Timeline API**
- Chronological event timeline
- Event filtering and sorting
- Timeline statistics

✅ **Phase 10: Image Search**
- Person Re-ID matching
- Similarity scoring
- YOLO + Re-ID integration

✅ **Phase 11: Text Search**
- CLIP-based semantic search
- Natural language queries
- Frame matching

✅ **Phase 12: Clip Service**
- FFmpeg clip extraction
- Event-based clip retrieval
- 30-second clips (±15s)

✅ **Complete Pipeline**
- Video upload
- Frame sampling (1 FPS)
- YOLO detection
- Object tracking
- Event generation
- Database storage

✅ **Frontend Dashboard**
- All API endpoints accessible
- Real-time testing
- JSON response display
- Video playback

---

## 📝 Sample Video Clips for Testing

Use any MP4 video file. For best results:
- Duration: 30-60 seconds
- Resolution: 720p or 1080p
- Content: People walking/moving
- Format: MP4 (H.264)

You can use:
- Sample videos from your phone
- Stock footage from Pexels/Pixabay
- Screen recordings

---

## 🎉 You're Ready!

1. Start backend (Terminal 1)
2. Start frontend (Terminal 2)
3. Open http://localhost:3000
4. Upload & process a video
5. Explore all the features!

**Enjoy testing TRACE!** 🚀
