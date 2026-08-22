"""
AERIX — Level 1 Traffic Detection & Tracking Tests

Covers:
1. Detection output schema (bbox, confidence, class_label, class_id, frame_number)
2. Traffic class mapping (person, car, motorcycle, bus, truck, bicycle; no false LGV/HGV)
3. ByteTrack Tracker:
   - Multi-object tracking simultaneously
   - Track ID persistence across frames
   - Missed detection / temporary occlusion buffering
   - Stationary / long dwell stability
4. TrackManager:
   - Trajectory and confidence history recording
   - Summary statistics and class counts
5. End-to-end traffic pipeline execution with synthetic video -> annotated MP4 output
"""

import os
import cv2
import pytest
import numpy as np
from pathlib import Path

from ml_pipeline.detection.yolo_detector import YOLODetector
from ml_pipeline.tracking.bytetrack import ByteTrackTracker
from ml_pipeline.tracking.track_manager import TrackManager
from ml_pipeline.traffic_pipeline import process_traffic_video


# ─────────────────────────────────────────────────────────────────────────────
# 1. Detection Output Schema & Class Mapping Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectionSchemaAndClasses:
    def test_detector_traffic_classes_honest_mapping(self):
        """Verify detector maps actual COCO traffic classes without inventing LGV/HGV."""
        classes = YOLODetector.get_supported_traffic_classes()
        assert 0 in classes and classes[0] == "person"
        assert 2 in classes and classes[2] == "car"
        assert 3 in classes and classes[3] == "motorcycle"
        assert 5 in classes and classes[5] == "bus"
        assert 7 in classes and classes[7] == "truck"
        # Ensure we do NOT claim separate LGV or HGV COCO IDs
        assert "lgv" not in [v.lower() for v in classes.values()]
        assert "hgv" not in [v.lower() for v in classes.values()]

    def test_mock_detect_traffic_schema(self):
        """Verify all detection fields match required schema."""
        detector = YOLODetector(use_real_yolo=False, confidence_threshold=0.3)
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        detections = detector.detect_traffic(dummy_frame, frame_number=42)
        assert len(detections) > 0

        for det in detections:
            assert "bbox" in det
            assert len(det["bbox"]) == 4
            x, y, w, h = det["bbox"]
            assert all(isinstance(v, (int, float)) for v in (x, y, w, h))
            assert w > 0 and h > 0

            assert "confidence" in det
            assert 0.0 <= det["confidence"] <= 1.0

            assert "class_label" in det
            assert det["class_label"] in ["person", "car", "motorcycle", "bus", "truck", "bicycle"]

            assert "class_id" in det
            assert "frame_number" in det
            assert det["frame_number"] == 42


# ─────────────────────────────────────────────────────────────────────────────
# 2. ByteTrack Tracking & Identity Stability Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestByteTrackTracker:
    def test_multi_object_simultaneous_tracking(self):
        """Verify multiple objects are tracked with distinct track IDs."""
        tracker = ByteTrackTracker(track_activation_threshold=0.2, frame_rate=10)
        
        # Frame 1: Two cars at distinct locations
        dets_frame_1 = [
            {"bbox": [100.0, 100.0, 50.0, 50.0], "confidence": 0.95, "class_label": "car", "class_id": 2},
            {"bbox": [300.0, 200.0, 60.0, 60.0], "confidence": 0.90, "class_label": "truck", "class_id": 7},
        ]
        tracked_1, lifecycle_1 = tracker.update(dets_frame_1, frame_number=1)
        
        assert len(tracked_1) == 2
        ids_1 = {t["track_id"] for t in tracked_1}
        assert len(ids_1) == 2  # Two distinct IDs

    def test_track_id_persistence_moving_object(self):
        """Verify the same physical vehicle retains its ID across consecutive frames."""
        tracker = ByteTrackTracker(track_activation_threshold=0.2, frame_rate=10)
        
        assigned_id = None
        for fn in range(1, 10):
            # Object moving smoothly 5px to the right each frame
            x = 100.0 + (fn * 5.0)
            dets = [{"bbox": [x, 150.0, 60.0, 40.0], "confidence": 0.92, "class_label": "car", "class_id": 2}]
            tracked, _ = tracker.update(dets, frame_number=fn)
            
            assert len(tracked) == 1
            if assigned_id is None:
                assigned_id = tracked[0]["track_id"]
            else:
                assert tracked[0]["track_id"] == assigned_id, f"ID changed from {assigned_id} to {tracked[0]['track_id']} at frame {fn}"

    def test_temporary_missed_detection_recovery(self):
        """Verify a short occlusion / missed detection does NOT immediately spawn a new track ID."""
        tracker = ByteTrackTracker(track_activation_threshold=0.2, lost_track_buffer=30, frame_rate=10)
        
        # Frame 1-3: Vehicle visible
        for fn in range(1, 4):
            dets = [{"bbox": [200.0, 200.0, 80.0, 50.0], "confidence": 0.90, "class_label": "bus", "class_id": 5}]
            tracked, _ = tracker.update(dets, frame_number=fn)
            initial_id = tracked[0]["track_id"]

        # Frame 4-5: Missed detections (occlusion)
        tracked_empty, lifecycle = tracker.update([], frame_number=4)
        assert len(tracked_empty) == 0
        tracker.update([], frame_number=5)

        # Frame 6: Re-appears at slightly updated position
        reappear_dets = [{"bbox": [210.0, 200.0, 80.0, 50.0], "confidence": 0.88, "class_label": "bus", "class_id": 5}]
        tracked_reappear, _ = tracker.update(reappear_dets, frame_number=6)
        
        assert len(tracked_reappear) == 1
        assert tracked_reappear[0]["track_id"] == initial_id, "Track ID was not preserved through occlusion"

    def test_stationary_vehicle_dwell_stability(self):
        """Verify stationary vehicles retain stable identity during long dwell times."""
        tracker = ByteTrackTracker(track_activation_threshold=0.2, frame_rate=10)
        
        initial_id = None
        for fn in range(1, 25):
            # Stationary vehicle
            dets = [{"bbox": [400.0, 300.0, 70.0, 70.0], "confidence": 0.93, "class_label": "truck", "class_id": 7}]
            tracked, _ = tracker.update(dets, frame_number=fn)
            assert len(tracked) == 1
            if initial_id is None:
                initial_id = tracked[0]["track_id"]
            else:
                assert tracked[0]["track_id"] == initial_id


# ─────────────────────────────────────────────────────────────────────────────
# 3. TrackManager History & Trajectory Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTrackManager:
    def test_track_manager_records_trajectory_and_history(self):
        """Verify TrackManager stores complete trajectory and confidence history."""
        manager = TrackManager()
        
        tracked_data = [
            {"track_id": 1, "bbox": [10.0, 20.0, 30.0, 40.0], "confidence": 0.95, "class_label": "car"},
            {"track_id": 2, "bbox": [100.0, 200.0, 50.0, 60.0], "confidence": 0.85, "class_label": "motorcycle"},
        ]
        manager.update(tracked_data, frame_number=1, video_fps=30)

        # Update track 1 in frame 2
        tracked_data_f2 = [
            {"track_id": 1, "bbox": [15.0, 20.0, 30.0, 40.0], "confidence": 0.92, "class_label": "car"},
        ]
        manager.update(tracked_data_f2, frame_number=2, video_fps=30)

        summary_1 = manager.get_summary(1)
        assert summary_1 is not None
        assert summary_1["track_id"] == 1
        assert summary_1["class_label"] == "car"
        assert summary_1["first_seen_frame"] == 1
        assert summary_1["last_seen_frame"] == 2
        assert summary_1["total_detections"] == 2
        assert len(summary_1["trajectory"]) == 2
        assert len(summary_1["confidence_history"]) == 2
        assert summary_1["trajectory"][0]["frame"] == 1
        assert summary_1["trajectory"][1]["frame"] == 2

        class_counts = manager.get_class_counts()
        assert class_counts == {"car": 1, "motorcycle": 1}

        points = manager.get_trajectory_points(1)
        assert len(points) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 4. End-to-End Pipeline & Annotated MP4 Output Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndPipeline:
    @pytest.fixture
    def synthetic_traffic_video(self, tmp_path):
        """Create a valid synthetic MP4 video file for pipeline testing."""
        video_path = tmp_path / "test_traffic.mp4"
        width, height, fps = 640, 480, 30
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
        
        # Write 30 frames (1 second) of video
        for i in range(30):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            # Draw synthetic road
            cv2.rectangle(frame, (100, 0), (540, 480), (50, 50, 50), -1)
            # Draw moving rectangle simulating vehicle
            x = 200 + i * 5
            cv2.rectangle(frame, (x, 200), (x + 80, 260), (0, 0, 200), -1)
            out.write(frame)
        out.release()
        
        return str(video_path)

    def test_pipeline_execution_and_annotated_video(self, synthetic_traffic_video, tmp_path):
        """Verify pipeline processes video, tracks objects, and creates playable annotated MP4."""
        output_path = tmp_path / "tracked_output.mp4"
        
        result = process_traffic_video(
            video_path=synthetic_traffic_video,
            output_path=str(output_path),
            sample_rate=3,
            confidence_threshold=0.3,
            use_real_yolo=False,  # Uses mock detector with moving cars, buses, pedestrians
            draw_trails=True,
        )
        
        assert result["status"] == "completed"
        assert result["frames_processed"] == 10  # 30 frames / sample_rate 3
        assert result["detections"] > 0
        assert result["unique_tracks"] > 0
        assert len(result["classes_detected"]) > 0
        assert os.path.exists(result["output_video"])
        
        # Verify annotated output video is valid and can be opened
        cap = cv2.VideoCapture(result["output_video"])
        assert cap.isOpened(), "Annotated output video could not be opened by OpenCV"
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        assert frame_count == 10, f"Expected 10 frames in annotated video, got {frame_count}"
        ret, frame = cap.read()
        assert ret and frame is not None and frame.shape == (480, 640, 3)
        cap.release()
