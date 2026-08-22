# AERIX — Autonomous Aerial Traffic Intelligence & Macroscopic Analytics Platform

**AERIX** is an AI-powered visual intelligence platform engineered for **Drone Traffic Detection, Fine-Grained Classification, Real-Unit Kinematics, and Macroscopic Spatial Analytics**.

---

## 🌟 Comprehensive Platform Capabilities

### 1. Macroscopic & Aggregate Traffic Analytics
- **Turning Movements & Intersection Flows**: Automated classification of turning maneuvers (`Through / Straight`, `Left Turn`, `Right Turn`, `U-Turn`) and directional approach volumes (`Northbound`, `Southbound`, `Eastbound`, `Westbound`).
- **Origin–Destination (O-D) Distributions**: Entry gate $\rightarrow$ Exit gate matrix with trip counts and route distribution percentages.
- **Segment-Wise Speed Profiles & Speeding Hotspots**: Corridor discretization computing Mean Speed, 85th Percentile Speed (P85), 15th Percentile Speed (P15), Speed Variance, and spatial speeding risk heatmaps.
- **Lane Volumes & Modal Split**: Lane-by-lane volume breakdown, average lane speed, and vehicle modal split percentages ($\% \text{Cars}, \% \text{Trucks}, \% \text{Buses}, \% \text{Motorcycles}$).
- **Queue Length & Delay Estimation**: Real-world standing queue lengths in meters, queued vehicle count, and average dwell delay behind stop lines and bottlenecks.
- **Density, Occupancy & Flow–Density (MFD) Relationships**: Traffic Density $k$ ($\text{veh/km}$), Road Area Occupancy percentage ($O\%$), Hourly Flow Rate $q$ ($\text{veh/hour}$), and Highway Capacity Manual Level of Service (LOS A to F).

### 2. Object-Level Insights & Fine-Grained Classification
- **Fine-Grained Sub-Types**:
  - `car` → `sedan`, `suv`, `hatchback`, `van`
  - `truck` → `lgv` (Light Goods Vehicle / Pickup / Van) vs `hgv` (Heavy Goods Vehicle / Semi / Box Truck)
  - `bus` → `minibus`, `transit_bus`, `coach_bus`
  - `motorcycle` → `scooter`, `motorcycle`
  - `person` → `pedestrian`
  - `bicycle` → `bicycle`
- **Real-Unit Kinematics Engine**:
  - Calculates per-object instantaneous and smoothed **velocity in real units** ($\text{m/s}$ and $\text{km/h}$).
  - Calculates per-object **acceleration in real units** ($\text{m/s}^2$).
  - Computes 8-point compass cardinal directions ($\text{N, NE, E, SE, S, SW, W, NW}$) and heading angles ($0^\circ - 360^\circ$).
  - Dynamic motion states (`Cruising`, `Accelerating`, `Braking`, `Stopped`).
  - Supports configurable metric scale (`--pixels-per-meter`, default $15.0\,\text{px/m}$) and Homography calibration.

### 3. Tracking & Visual Analytics
- **ByteTrack Persistent Identity**: High-performance multi-object tracking using Kalman motion state estimation and Hungarian assignment algorithms.
- **Trajectory Trails & Velocity Vectors**: Dynamic motion history trails and directional velocity vectors rendered on output videos.
- **Interactive Web Dashboard**: Single-page dark-themed analytics interface (`http://localhost:8888`) with real-time Macroscopic Intelligence panels, turning movement charts, O-D matrix, speed profiles, and a live searchable Object Telemetry Table.

---

## 🏗️ Technical Architecture

### Analytics & Computer Vision Pipeline (`ml_pipeline/`)
- **YOLOv8 (`yolo_detector.py`)**: Multi-class traffic detection with configurable confidence thresholds.
- **Fine-Grained Classifier (`fine_grained.py`)**: Geometric and visual sub-classifier resolving vehicle subtypes.
- **Kinematics Engine (`kinematics.py`)**: Real-unit physics state estimator for velocity, acceleration, and heading vectors.
- **Macroscopic Analytics Engine (`aggregate_analytics.py`)**: Computes turning movements, O-D flows, speed profiles, lane modal split, queues, density, occupancy, and LOS.
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
Open **`http://localhost:8888`** in your browser to view the interactive dashboard.

### 2. Run Command Line Pipeline
```powershell
python -m ml_pipeline.traffic_pipeline --video "path/to/drone_video.mp4" --output "storage/videos/level1_output.mp4" --json-output "level1_results.json" --sample-rate 3 --confidence 0.3 --pixels-per-meter 15.0
```

### 3. Run Automated Test Suite
```powershell
python -m pytest tests/test_aggregate_traffic_analytics.py tests/test_kinematics_and_fine_grained.py tests/test_traffic_detection.py -v
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