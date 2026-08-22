# AERIX — Traffic Detection & Tracking Platform (Level 1)

**AERIX** is an AI-powered visual intelligence platform adapted from TRACE, engineered for **Level 1 Aerial Drone Traffic Detection and Multi-Object Tracking**.

---

## 🌟 Level 1 Core Capabilities

- **Multi-Class Road User Detection**: Detects `car`, `truck` (LGV/HGV), `bus`, `motorcycle`, `person` (pedestrian), and `bicycle`.
- **ByteTrack Persistent Identity**: High-performance multi-object tracking using Kalman motion state estimation and Hungarian assignment algorithms.
- **Occlusion & Dwell Stability**: Maintains stable track IDs across short temporary occlusions, vehicle path crossings, and long dwell times at traffic signals.
- **Trajectory Trails**: Dynamic motion history trails rendered per vehicle on output videos (`level1_output.mp4`).
- **Interactive Web Dashboard**: Single-page dark-themed analytics interface (`http://localhost:8888`) displaying real-time FPS, total detections, unique track counts, and class distribution charts.
- **Standalone Execution**: Can run standalone without a database requirement.

---

## 🏗️ Technical Architecture

### Computer Vision Pipeline (`ml_pipeline/`)
- **YOLOv8 (`yolo_detector.py`)**: Multi-class traffic detection with configurable confidence thresholds.
- **ByteTrack (`bytetrack.py`)**: Two-stage association tracking wrapping `supervision.ByteTrack`.
- **TrackManager (`track_manager.py`)**: In-memory track history maintaining per-frame bounding boxes, confidence histories, and timestamps.
- **TrafficPipeline (`traffic_pipeline.py`)**: Standalone pipeline orchestrator handling video ingestion, frame sampling, tracking, and annotated MP4 video output.

### Web Server & Dashboard (`demo_server.py`, `demo_frontend.html`)
- **HTTP Server**: Pure Python HTTP server serving the interactive web dashboard on port `8888`.
- **REST Endpoints**: `/api/results`, `/api/upload`, `/api/process`, `/api/status`.

---

## ⚡ Quick Start

### 1. Run the Web Dashboard
```powershell
python demo_server.py
```
Open **`http://localhost:8888`** in your browser to view the interactive dashboard, upload videos, and inspect tracking analytics.

### 2. Run Command Line Pipeline
```powershell
python -m ml_pipeline.traffic_pipeline --video "path/to/drone_video.mp4" --output "storage/videos/level1_output.mp4" --json-output "level1_results.json" --sample-rate 3 --confidence 0.3
```

### 3. Run Automated Test Suite
```powershell
python -m pytest tests/test_traffic_detection.py -v
```

---

## 📊 Summary Output Format (`level1_results.json`)

```json
{
  "video_id": "drone_traffic_01",
  "status": "completed",
  "frames_processed": 2400,
  "detections": 12480,
  "unique_tracks": 179,
  "classes_detected": ["bus", "car", "motorcycle", "person", "truck"],
  "class_counts": {
    "car": 124,
    "truck": 18,
    "motorcycle": 28,
    "bus": 4,
    "person": 5
  },
  "average_confidence": 0.9142,
  "output_video": "storage/videos/level1_output.mp4"
}
```

---

## 📋 Honest Model Limitations (COCO Benchmark)

1. **LGV vs. HGV**: Standard COCO models do not distinguish Light Goods Vehicles from Heavy Goods Vehicles natively. All goods vehicles are accurately categorized as `truck`.
2. **Single Camera**: Tracking is bounded to single-camera views (Level 1 scope).