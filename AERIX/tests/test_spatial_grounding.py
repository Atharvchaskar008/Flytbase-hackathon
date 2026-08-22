"""AERIX — Spatial Grounding & Map-Native Topology Test Suite"""

import pytest
import numpy as np
from ml_pipeline.spatial.srt_parser import SRTTelemetryParser, DroneFrameTelemetry
from ml_pipeline.spatial.ground_projector import GroundProjector
from ml_pipeline.spatial.road_network import RoadNetworkModel
from ml_pipeline.spatial.spatial_grounding_engine import SpatialGroundingEngine


class TestSRTTelemetryParser:
    """Test SRT parsing and telemetry generation."""

    def test_default_telemetry_generation(self):
        parser = SRTTelemetryParser(default_lat=37.774929, default_lon=-122.419416, default_altitude_m=85.0)
        telem = parser.get_telemetry_for_frame(frame_number=0, fps=30.0)

        assert isinstance(telem, DroneFrameTelemetry)
        assert abs(telem.latitude - 37.774929) < 1e-4
        assert abs(telem.longitude - (-122.419416)) < 1e-4
        assert telem.relative_altitude_m > 80.0
        assert telem.gimbal_pitch_deg < -80.0


class TestGroundProjector:
    """Test 3D pinhole camera ray projection and metric/GPS conversion."""

    def test_center_pixel_nadir_projection(self):
        projector = GroundProjector(frame_shape=(720, 1280), default_hfov_deg=84.0)
        telem = DroneFrameTelemetry(
            frame_index=0,
            timestamp=0.0,
            iso_timestamp="2026-08-22T12:00:00Z",
            latitude=37.774929,
            longitude=-122.419416,
            relative_altitude_m=85.0,
            absolute_altitude_m=110.0,
            gimbal_pitch_deg=-90.0,  # Nadir
            gimbal_roll_deg=0.0,
            gimbal_yaw_deg=0.0,
        )

        # Center pixel (640, 360) at Nadir should project directly underneath drone
        east_m, north_m = projector.pixel_to_ground_metric(640, 360, telem)
        assert abs(east_m) < 1.0
        assert abs(north_m) < 1.0

        lat, lon = projector.pixel_to_gps(640, 360, telem)
        assert abs(lat - 37.774929) < 1e-5
        assert abs(lon - (-122.419416)) < 1e-5

    def test_camera_footprint_polygon(self):
        projector = GroundProjector(frame_shape=(720, 1280))
        telem = DroneFrameTelemetry(
            frame_index=0, timestamp=0.0, iso_timestamp="",
            latitude=37.774929, longitude=-122.419416,
            relative_altitude_m=85.0, absolute_altitude_m=110.0,
            gimbal_pitch_deg=-90.0, gimbal_roll_deg=0.0, gimbal_yaw_deg=0.0
        )

        footprint = projector.compute_camera_view_footprint_geojson(telem)
        assert footprint["type"] == "Feature"
        coords = footprint["geometry"]["coordinates"][0]
        assert len(coords) == 5  # closed polygon


class TestRoadNetworkModel:
    """Test road network topology, trajectory binding, desire lines, and queue extents."""

    def test_snap_point_to_network(self):
        model = RoadNetworkModel(center_lat=37.774929, center_lon=-122.419416)
        
        # Test point near north inbound lane
        north_lat = 37.774929 + 0.0004
        north_lon = -122.419416 + 0.00003

        snap = model.snap_point_to_network(north_lat, north_lon)
        assert snap["link_id"] in ["north", "south", "east", "west", "intersection_core"]
        assert "lane_id" in snap
        assert "approach" in snap

    def test_desire_lines_and_queue_extents_geojson(self):
        model = RoadNetworkModel(center_lat=37.774929, center_lon=-122.419416)
        od_matrix = {
            "major_corridors": [
                {"origin": "North Approach", "destination": "South Approach", "volume": 12, "proportion_pct": 45.0},
                {"origin": "East Approach", "destination": "West Approach", "volume": 8, "proportion_pct": 30.0},
            ]
        }

        desire = model.generate_desire_lines_geojson(od_matrix)
        assert desire["type"] == "FeatureCollection"
        assert len(desire["features"]) == 2

        # Test queue extents
        mock_tracks = [{
            "track_id": 1,
            "fine_grained_class": "sedan",
            "kinematics": {"current_speed_kmh": 2.0},
            "geodetic_position": {
                "latitude": 37.774929 + 0.0003,
                "longitude": -122.419416 + 0.00003,
                "lane_id": "north_inbound_lane_1",
                "distance_to_intersection_m": 25.0,
            }
        }]

        queues = model.compute_queue_extents_geojson(mock_tracks)
        assert queues["type"] == "FeatureCollection"
        assert len(queues["features"]) >= 1


class TestSpatialGroundingEngine:
    """Test end-to-end Spatial Grounding Engine."""

    def test_spatial_grounding_end_to_end(self):
        engine = SpatialGroundingEngine(center_lat=37.774929, center_lon=-122.419416)

        mock_objects = [{
            "track_id": 10,
            "bbox": [600, 300, 80, 50],
            "confidence": 0.92,
            "class_label": "car",
            "kinematics": {"heading_degrees": 180.0},
        }]

        telemetry, grounded = engine.process_frame_tracks(mock_objects, frame_number=1, fps=30.0)
        assert len(grounded) == 1
        assert "geodetic_position" in grounded[0]
        geo = grounded[0]["geodetic_position"]
        assert "latitude" in geo and "longitude" in geo
        assert "lane_id" in geo

        # Test report generation
        report = engine.generate_map_native_analytics(grounded, last_frame_number=1, fps=30.0)
        assert report["is_spatially_grounded"] is True
        assert "road_network_geojson" in report
        assert "desire_lines_geojson" in report
        assert "queue_extents_geojson" in report
