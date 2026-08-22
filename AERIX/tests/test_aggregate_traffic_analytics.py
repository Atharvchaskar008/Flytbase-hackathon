"""
AERIX — Macroscopic & Spatial Traffic Analytics Test Suite

Tests:
1. Intersection Turning Movements & Classified Directional Volume
2. Origin–Destination (O-D) Distribution Matrix
3. Segment Speed Profiles (Mean, P85, P15) and Speeding Hotspot Detection
4. Lane Volumes and Modal Split Percentages
5. Queue Length (in real meters) and Dwell Delay Estimation
6. Density (veh/km), Occupancy (%), Hourly Flow Rate (veh/h), and Level of Service (LOS)
"""

import math
import numpy as np
import pytest

from ml_pipeline.analytics.aggregate_analytics import MacroTrafficAnalyticsEngine
from ml_pipeline.traffic_pipeline import process_traffic_video


# ─────────────────────────────────────────────────────────────────────────────
# 1. Turning Movement & Directional Volume Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTurningMovements:
    def test_straight_through_movement(self):
        """Test straight trajectory classification."""
        engine = MacroTrafficAnalyticsEngine()
        # Trajectory moving straight west to east
        straight_track = [{
            "track_id": 1,
            "class_label": "car",
            "fine_grained_class": "sedan",
            "trajectory": [
                {"bbox": [100.0 + (i * 50.0), 360.0, 80.0, 40.0]} for i in range(10)
            ],
        }]
        res = engine.compute_turning_movements(straight_track, frame_shape=(720, 1280))
        assert res["movement_counts"]["Through (Straight)"] == 1
        assert res["approach_directional_volumes"]["Eastbound"] == 1

    def test_turning_movements_left_and_right(self):
        """Test turning maneuver classification."""
        engine = MacroTrafficAnalyticsEngine()
        
        # Vehicle turns from Eastbound into Southbound (Right turn in image coordinates)
        right_turn_track = {
            "track_id": 2,
            "class_label": "truck",
            "fine_grained_class": "hgv",
            "trajectory": [
                {"bbox": [200.0, 300.0, 100.0, 60.0]},
                {"bbox": [300.0, 300.0, 100.0, 60.0]},
                {"bbox": [400.0, 320.0, 100.0, 60.0]},
                {"bbox": [420.0, 420.0, 60.0, 100.0]},
                {"bbox": [420.0, 550.0, 60.0, 100.0]},
            ]
        }
        res = engine.compute_turning_movements([right_turn_track], frame_shape=(720, 1280))
        assert res["movement_counts"]["Right Turn"] == 1
        assert res["total_movements_analyzed"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. Origin–Destination Matrix Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOriginDestinationMatrix:
    def test_od_matrix_flows(self):
        """Test O-D matrix flow mapping from North to South approach."""
        engine = MacroTrafficAnalyticsEngine()
        tracks = [
            {
                "track_id": i,
                "class_label": "car",
                "trajectory": [
                    {"bbox": [640.0, 20.0, 50.0, 30.0]},  # Entry near North border
                    {"bbox": [640.0, 700.0, 50.0, 30.0]}, # Exit near South border
                ],
            }
            for i in range(5)
        ]
        od = engine.compute_origin_destination_matrix(tracks, frame_shape=(720, 1280))
        assert od["total_trips"] == 5
        assert od["od_matrix_counts"]["North Approach"]["South Approach"] == 5
        assert od["od_matrix_percentages"]["North Approach"]["South Approach"] == 100.0


# ─────────────────────────────────────────────────────────────────────────────
# 3. Segment Speed Profiles & Hotspots Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSegmentSpeedProfiles:
    def test_speed_profiles_and_speeding_hotspots(self):
        """Test spatial segment speed statistics (mean, p85, p15) and speeding detection."""
        engine = MacroTrafficAnalyticsEngine(speed_limit_kmh=50.0, pixels_per_meter=10.0)
        
        # 5 vehicles speeding in Segment 1 (x: 0 to 256px), normal in other segments
        tracks = []
        for i in range(10):
            spd = 75.0 if i < 4 else 45.0  # 40% speeding
            tracks.append({
                "track_id": i,
                "kinematics": {"current_speed_kmh": spd, "average_speed_kmh": spd},
                "trajectory": [{"bbox": [50.0, 300.0, 50.0, 30.0]}],  # In segment 1
            })

        prof = engine.compute_segment_speed_profiles(tracks, frame_shape=(720, 1280), num_segments=5)
        seg1 = prof["segment_profiles"][0]
        assert seg1["sample_count"] == 10
        assert seg1["p85_speed_kmh"] >= 70.0
        assert seg1["speeding_percentage"] == 40.0
        assert seg1["risk_level"] == "High"
        assert len(prof["speeding_hotspots"]) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# 4. Lane Volumes & Modal Split Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLaneVolumeAndModalSplit:
    def test_lane_volumes_and_modal_distribution(self):
        """Test lane classification and vehicle type modal split percentages."""
        engine = MacroTrafficAnalyticsEngine()
        
        # Lane 1 (top y: 0-240): 4 Cars, 1 Motorcycle
        tracks = []
        for i in range(4):
            tracks.append({
                "track_id": i,
                "fine_grained_class": "sedan",
                "class_label": "car",
                "kinematics": {"average_speed_kmh": 60.0},
                "trajectory": [{"bbox": [500.0, 100.0, 50.0, 30.0]}],
            })
        tracks.append({
            "track_id": 99,
            "fine_grained_class": "motorcycle",
            "class_label": "motorcycle",
            "kinematics": {"average_speed_kmh": 55.0},
            "trajectory": [{"bbox": [500.0, 100.0, 30.0, 20.0]}],
        })

        lane_res = engine.compute_lane_volumes_and_modal_split(tracks, frame_shape=(720, 1280), num_lanes=3)
        lane1 = lane_res["lanes"][0]
        assert lane1["volume"] == 5
        assert lane1["modal_split_pct"]["sedan"] == 80.0
        assert lane1["modal_split_pct"]["motorcycle"] == 20.0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Queue Length & Delay Estimation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestQueueLengthEstimation:
    def test_queue_detection_and_length_meters(self):
        """Test standing queue length calculation in real meters."""
        # Scale: 10 px = 1 meter
        engine = MacroTrafficAnalyticsEngine(queue_speed_threshold_kmh=5.0, pixels_per_meter=10.0)

        # 4 vehicles lined up bumper-to-bumper spanning x=100 to x=400 (300px = 30 meters)
        queued_tracks = []
        for i, x in enumerate([100.0, 200.0, 300.0, 400.0]):
            queued_tracks.append({
                "track_id": i + 1,
                "fine_grained_class": "sedan",
                "duration_frames": 90,  # 3 seconds duration
                "kinematics": {"current_speed_kmh": 1.0, "average_speed_kmh": 1.2},
                "trajectory": [{"bbox": [x, 300.0, 60.0, 30.0]}],
            })

        q_res = engine.compute_queue_lengths(queued_tracks, fps=30.0, sample_rate=1)
        assert q_res["active_queues_detected"] == 1
        assert q_res["total_queued_vehicles"] == 4
        assert q_res["max_queue_length_meters"] == pytest.approx(30.0, abs=1.0)
        assert q_res["queuing_status"] in ["Moderate Queue", "Severe Congestion Queue"]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Density, Occupancy & Flow Rate Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDensityOccupancyAndFlow:
    def test_macroscopic_flow_and_density(self):
        """Test traffic density (k), road area occupancy (O%), flow (q), and LOS."""
        engine = MacroTrafficAnalyticsEngine(pixels_per_meter=10.0)
        # 1280px = 128 meters = 0.128 km
        tracks = [
            {
                "track_id": i,
                "kinematics": {"average_speed_kmh": 55.0},
                "trajectory": [{"bbox": [i * 50.0, 300.0, 50.0, 30.0]}],
            }
            for i in range(10)
        ]
        # 10 vehicles in 15 seconds (150 frames @ 10 fps)
        flow = engine.compute_density_occupancy_flow(
            tracks=tracks,
            frames_processed=150,
            fps=30.0,
            sample_rate=3,
            frame_shape=(720, 1280),
        )
        assert flow["density_vehicles_per_km"] > 0
        assert flow["road_area_occupancy_pct"] > 0.0
        assert flow["hourly_flow_rate_veh_hour"] > 0
        assert "LOS" in flow["level_of_service"]
        assert "Branch" in flow["mfd_congestion_state"] or "Flow" in flow["mfd_congestion_state"]


# ─────────────────────────────────────────────────────────────────────────────
# 7. End-to-End Pipeline Macroscopic Integration Test
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndPipelineMacroscopic:
    def test_pipeline_includes_macroscopic_analytics(self, tmp_path):
        """Verify pipeline execution generates complete macroscopic_analytics in output dict."""
        import cv2
        test_video = str(tmp_path / "drone_macro_test.mp4")
        test_output = str(tmp_path / "drone_macro_out.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(test_video, fourcc, 10, (640, 480))
        for _ in range(12):
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
        assert "macroscopic_analytics" in result
        macro = result["macroscopic_analytics"]
        assert "turning_movements" in macro
        assert "origin_destination_matrix" in macro
        assert "speed_profiles" in macro
        assert "lane_analytics" in macro
        assert "queue_analytics" in macro
        assert "macroscopic_flow" in macro
