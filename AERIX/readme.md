# AERIX — Traffic Intelligence & Object-Level Kinematics Platform

**AERIX** is an AI-powered visual intelligence platform engineered for **Aerial Drone Traffic Detection, Fine-Grained Classification, Multi-Object Tracking, and Real-Unit Kinematics**.

---

## 🌟 Core Capabilities

- **Object-Level Insights & Fine-Grained Classification**:
  - `car` → `sedan`, `suv`, `hatchback`, `van`
  - `truck` → `lgv` (Light Goods Vehicle / Pickup / Delivery Van) vs `hgv` (Heavy Goods Vehicle / Semi / Box Truck)
  - `bus` → `minibus`, `transit_bus`, `coach_bus`
  - `motorcycle` → `scooter`, `motorcycle`
  - `person` → `pedestrian`
  - `bicycle` → `bicycle`
- **Real-Unit Kinematics Engine**:
  - Calculates per-object instantaneous and smoothed **velocity in real units** ($\text{m/s}$ and $\text{km/h}$).
  - Calculates per-object **acceleration in real units** ($\text{m/s}^2$).
  - Computes 8-point compass cardinal directions ($\text{N, NE, E, SE, S, SW, W, NW}$) and heading angles ($0^\circ - 360^\circ$).
  - Classifies dynamic motion status (`Cruising`, `Accelerating`, `Braking`, `Stopped`).
  - Supports configurable metric scale (`--pixels-per-meter`, default $15.0\,\text{px/m}$) and Homography perspective matrix calibration.
- **ByteTrack Persistent Identity**: High-performance multi-object tracking using Kalman motion state estimation and Hungarian assignment algorithms.
- **Occlusion & Dwell Stability**: Maintains stable track IDs across short temporary occlusions, vehicle path crossings, and long dwell times at traffic signals.
- **Trajectory Trails & Velocity Vectors**: Dynamic motion history trails and directional velocity vectors rendered on output videos.
- **Interactive Web Dashboard**: Single-page dark-themed analytics interface (`http://localhost:8888`) with real-time Fleet Kinematics stats, Fine-Grained breakdown, and a live searchable Object Telemetry Table.
- **Standalone Execution**: Runs completely standalone with zero database setup required.

---

## 🏗️ Technical Architecture

### Computer Vision & Kinematics Pipeline (`ml_pipeline/`)
- **YOLOv8 (`yolo_detector.py`)**: Multi-class traffic detection with configurable confidence thresholds.
- **Fine-Grained Classifier (`fine_grained.py`)**: Geometric and visual sub-classifier resolving vehicle subtypes.
- **Kinematics Engine (`kinematics.py`)**: Real-unit physics state estimator for velocity, acceleration, and heading vectors.
- **ByteTrack (`bytetrack.py`)**: Two-stage association tracking wrapping `supervision.ByteTrack`.
- **TrackManager (`track_manager.py`)**: In-memory track history maintaining per-frame bounding boxes, confidence histories, kinematics telemetry, and timestamps.
- **TrafficPipeline (`traffic_pipeline.py`)**: Standalone pipeline orchestrator handling video ingestion, frame sampling, tracking, physics annotation, and MP4 video output.

### Web Server & Dashboard (`demo_server.py`, `demo_frontend.html`)
- **HTTP Server**: Pure Python HTTP server serving the interactive web dashboard on port `8888`.
- **REST Endpoints**: `/api/results`, `/api/upload`, `/api/process`, `/api/status`.

---

## ⚡ Quick Start

### 1. Run the Web Dashboard
```powershell
python demo_server.py
```
Open **`http://localhost:8888`** in your browser to view the interactive dashboard, inspect fine-grained vehicle types, and review per-object velocity & acceleration telemetry.

### 2. Run Command Line Pipeline
```powershell
python -m ml_pipeline.traffic_pipeline --video "path/to/drone_video.mp4" --output "storage/videos/level1_output.mp4" --json-output "level1_results.json" --sample-rate 3 --confidence 0.3 --pixels-per-meter 15.0
```

### 3. Run Automated Test Suite
```powershell
python -m pytest tests/test_kinematics_and_fine_grained.py tests/test_traffic_detection.py -v
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
  "fine_grained_class_counts": {
    "sedan": 82,
    "suv": 34,
    "van": 8,
    "lgv": 12,
    "hgv": 6,
    "transit_bus": 4,
    "motorcycle": 28,
    "pedestrian": 5
  },
  "kinematics_summary": {
    "average_speed_kmh": 42.6,
    "max_speed_kmh": 68.4,
    "speeding_count": 5,
    "stopped_count": 14,
    "active_moving_count": 165
  },
  "pixels_per_meter": 15.0,
  "average_confidence": 0.9142,
  "output_video": "storage/videos/level1_output.mp4"
}
```