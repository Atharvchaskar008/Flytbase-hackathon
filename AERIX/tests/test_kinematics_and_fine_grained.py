"""
AERIX — Object-Level Insight & Kinematics Test Suite

Tests:
1. Fine-Grained Vehicle Classification (Sedan, SUV, Hatchback, Van, LGV, HGV, Bus, etc.)
2. Kinematics Physics Calculations (Velocity in m/s and km/h, Acceleration in m/s², Heading)
3. Trajectory Smoothing & Metric Scaling (pixels_per_meter, Homography transformation)
4. TrackManager Kinematics & Fine-Grained Record Integration
5. End-to-End Traffic Pipeline with Kinematic Output and Metadata
"""

import math
import numpy as np
import pytest

from ml_pipeline.detection.fine_grained import FineGrainedClassifier
from ml_pipeline.tracking.kinematics import KinematicsCalculator
from ml_pipeline.tracking.track_manager import TrackManager
from ml_pipeline.traffic_pipeline import process_traffic_video


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fine-Grained Vehicle Subclassification Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFineGrainedClassification:
    def test_car_subclassification(self):
        """Test car subdivision into sedan, suv, hatchback, van."""
        # Long profile -> sedan
        res_sedan = FineGrainedClassifier.classify("car", [100, 100, 160, 60], confidence=0.92)
        assert res_sedan["fine_grained_class"] == "sedan"
        assert res_sedan["parent_class"] == "car"

        # Large boxy profile -> suv
        res_suv = FineGrainedClassifier.classify("car", [100, 100, 120, 90], confidence=0.95)
        assert res_suv["fine_grained_class"] in ["suv", "van"]

        # Small compact profile -> hatchback
        res_hatch = FineGrainedClassifier.classify("car", [100, 100, 65, 50], confidence=0.88)
        assert res_hatch["fine_grained_class"] in ["hatchback", "sedan"]

    def test_truck_lgv_vs_hgv(self):
        """Test truck subclassification into LGV (Light Goods) and HGV (Heavy Goods)."""
        # Light Goods Vehicle (small pickup / delivery truck)
        res_lgv = FineGrainedClassifier.classify("truck", [100, 100, 100, 60], confidence=0.91)
        assert res_lgv["fine_grained_class"] == "lgv"

        # Heavy Goods Vehicle (massive 18-wheeler / semi-trailer)
        res_hgv = FineGrainedClassifier.classify("truck", [100, 100, 220, 90], confidence=0.94)
        assert res_hgv["fine_grained_class"] == "hgv"

    def test_bus_subclassification(self):
        """Test bus subclassification into minibus, transit_bus, coach_bus."""
        # Small minibus
        res_mini = FineGrainedClassifier.classify("bus", [100, 100, 80, 45], confidence=0.89)
        assert res_mini["fine_grained_class"] == "minibus"

        # Standard transit city bus
        res_transit = FineGrainedClassifier.classify("bus", [100, 100, 150, 70], confidence=0.93)
        assert res_transit["fine_grained_class"] in ["transit_bus", "coach_bus"]

    def test_pedestrian_and_vulnerable_road_users(self):
        """Test pedestrian, scooter, and bicycle classifications."""
        res_ped = FineGrainedClassifier.classify("person", [100, 100, 30, 80], confidence=0.90)
        assert res_ped["fine_grained_class"] == "pedestrian"

        res_bike = FineGrainedClassifier.classify("bicycle", [100, 100, 40, 50], confidence=0.85)
        assert res_bike["fine_grained_class"] == "bicycle"

        res_scooter = FineGrainedClassifier.classify("motorcycle", [100, 100, 35, 40], confidence=0.87)
        assert res_scooter["fine_grained_class"] in ["scooter", "motorcycle"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Kinematics Physics Calculations Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestKinematicsCalculator:
    def test_constant_velocity_linear_motion(self):
        """Test that a vehicle moving at constant speed produces correct real-world m/s and km/h."""
        # Scale: 10 pixels = 1 meter
        calc = KinematicsCalculator(pixels_per_meter=10.0, smoothing_alpha=1.0)
        
        # Vehicle moves 20 pixels per second (2.0 m/s = 7.2 km/h) heading East
        # 10 fps -> 2 pixels per frame
        trajectory = []
        fps = 10.0
        for i in range(11):
            t = i * 0.1  # 0.0, 0.1, 0.2 ... 1.0s
            x = 100.0 + (i * 2.0)  # +2px per step -> 20px in 1s -> 2m in 1s = 2.0 m/s
            trajectory.append({
                "frame": i,
                "timestamp": round(t, 2),
                "bbox": [x, 200.0, 50.0, 30.0],
            })

        kin = calc.calculate_kinematics(trajectory, fps=fps)
        assert kin["current_speed_ms"] == pytest.approx(2.0, abs=0.1)
        assert kin["current_speed_kmh"] == pytest.approx(7.2, abs=0.4)
        assert kin["cardinal_direction"] == "E"
        assert kin["motion_status"] == "Cruising"

    def test_accelerating_vehicle(self):
        """Test acceleration calculation (m/s²) when vehicle accelerates."""
        calc = KinematicsCalculator(pixels_per_meter=10.0, smoothing_alpha=1.0)
        fps = 10.0
        dt = 1.0 / fps

        # Position under constant acceleration: x(t) = 0.5 * a * t^2
        # Let a = 2.0 m/s² = 20 px/s²
        trajectory = []
        for i in range(15):
            t = i * dt
            # x = 0.5 * 20 * t^2 = 10 * t^2 (in pixels)
            x_px = 100.0 + (10.0 * t * t)
            trajectory.append({
                "frame": i,
                "timestamp": round(t, 3),
                "bbox": [x_px, 200.0, 50.0, 30.0],
            })

        kin = calc.calculate_kinematics(trajectory, fps=fps)
        assert kin["current_acceleration_ms2"] > 0.5
        assert kin["motion_status"] in ["Accelerating", "Cruising"]

    def test_stopped_vehicle(self):
        """Test stationary vehicle produces 0 speed and 'Stopped' status."""
        calc = KinematicsCalculator(pixels_per_meter=15.0)
        trajectory = [
            {"frame": i, "timestamp": i * 0.1, "bbox": [100.0, 100.0, 50.0, 30.0]}
            for i in range(10)
        ]
        kin = calc.calculate_kinematics(trajectory, fps=10.0)
        assert kin["current_speed_kmh"] == 0.0
        assert kin["motion_status"] == "Stopped"

    def test_homography_perspective_transformation(self):
        """Test metric coordinate transformation with custom homography matrix."""
        # Simple diagonal scaling homography matrix
        H = np.array([
            [0.1, 0.0, 0.0],
            [0.0, 0.1, 0.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)
        calc = KinematicsCalculator(homography_matrix=H)
        mx, my = calc.pixel_to_metric(100.0, 200.0)
        assert mx == pytest.approx(10.0, abs=0.01)
        assert my == pytest.approx(20.0, abs=0.01)


# ─────────────────────────────────────────────────────────────────────────────
# 3. TrackManager Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTrackManagerKinematics:
    def test_track_manager_updates_kinematics_and_fine_grained(self):
        """Verify TrackManager updates kinematic telemetry and subclassification automatically."""
        tm = TrackManager(pixels_per_meter=10.0, sample_rate=1)

        # Update frame 1
        objs_f1 = [{
            "track_id": 1,
            "bbox": [100.0, 100.0, 150.0, 60.0],  # Car (Sedan)
            "confidence": 0.95,
            "class_label": "car",
        }]
        tm.update(objs_f1, frame_number=1, video_fps=10)

        # Update frame 2 (moved 10px right = 1 meter in 0.1s = 10 m/s = 36 km/h)
        objs_f2 = [{
            "track_id": 1,
            "bbox": [110.0, 100.0, 150.0, 60.0],
            "confidence": 0.96,
            "class_label": "car",
        }]
        tm.update(objs_f2, frame_number=2, video_fps=10)

        summary = tm.get_summary(1)
        assert summary is not None
        assert summary["fine_grained_class"] == "sedan"
        assert "kinematics" in summary
        assert summary["kinematics"]["current_speed_kmh"] > 0.0

        fg_counts = tm.get_fine_grained_class_counts()
        assert "sedan" in fg_counts
        assert fg_counts["sedan"] == 1

        kin_fleet = tm.get_kinematics_summary()
        assert kin_fleet["max_speed_kmh"] > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. End-to-End Pipeline Integration Test
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineWithKinematics:
    def test_mock_pipeline_produces_kinematics_output(self, tmp_path):
        """Run process_traffic_video and verify result dictionary contains kinematics and fine-grained classes."""
        import cv2
        # Create a tiny 15-frame synthetic video
        test_video = str(tmp_path / "drone_kinematics_test.mp4")
        test_output = str(tmp_path / "drone_kinematics_out.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(test_video, fourcc, 10, (640, 480))
        for _ in range(15):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

        result = process_traffic_video(
            video_path=test_video,
            output_path=test_output,
            sample_rate=1,
            confidence_threshold=0.3,
            use_real_yolo=False,
            pixels_per_meter=15.0,
        )

        assert result["status"] == "completed"
        assert "kinematics_summary" in result
        assert "fine_grained_class_counts" in result
        assert "tracks" in result
        assert len(result["tracks"]) > 0

        # Check that individual track records have kinematics
        for track in result["tracks"]:
            assert "kinematics" in track
            assert "fine_grained_class" in track
            assert "current_speed_kmh" in track["kinematics"]
            assert "current_acceleration_ms2" in track["kinematics"]
