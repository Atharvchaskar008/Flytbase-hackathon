"""AERIX — Spatial Grounding Engine

Master orchestrator for recovering ground-plane projection and binding every trajectory
to the road network itself:
- Telemetry Ingestion (SRT / Subtitles / GPS / Gimbal / Altitude)
- Ground-Plane Projection (Camera Ray Intersection & Metric to WGS84 Geodetic)
- Road Network Binding (Link, Approach, Direction, Lane moment-to-moment)
- Map-Native Outputs (Desire Lines, Queue Extents along Carriageway, Per-Lane Metrics)
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np

from .srt_parser import SRTTelemetryParser, DroneFrameTelemetry
from .ground_projector import GroundProjector
from .road_network import RoadNetworkModel


class SpatialGroundingEngine:
    """End-to-end spatial grounding and road network binding system."""

    def __init__(
        self,
        srt_path: Optional[Union[str, Path]] = None,
        center_lat: float = 37.774929,
        center_lon: float = -122.419416,
        default_altitude_m: float = 85.0,
        default_pitch_deg: float = -90.0,
        default_yaw_deg: float = 0.0,
        frame_shape: Tuple[int, int] = (720, 1280),
        horizontal_fov_deg: float = 84.0,
    ):
        """Initialize Spatial Grounding Engine."""
        self.srt_parser = SRTTelemetryParser(
            srt_path=srt_path,
            default_lat=center_lat,
            default_lon=center_lon,
            default_altitude_m=default_altitude_m,
            default_pitch_deg=default_pitch_deg,
            default_yaw_deg=default_yaw_deg,
            horizontal_fov_deg=horizontal_fov_deg,
        )

        self.projector = GroundProjector(
            frame_shape=frame_shape,
            default_hfov_deg=horizontal_fov_deg,
        )

        self.road_network = RoadNetworkModel(
            center_lat=center_lat,
            center_lon=center_lon,
            arm_length_meters=120.0,
            lane_width_meters=3.5,
            num_lanes_per_direction=2,
        )

    def process_frame_tracks(
        self,
        tracked_objects: List[Dict[str, Any]],
        frame_number: int,
        fps: float = 30.0,
    ) -> Tuple[DroneFrameTelemetry, List[Dict[str, Any]]]:
        """Ground and bind all tracked vehicles in the current frame to the road network.

        Args:
            tracked_objects: List of tracking dicts with 'track_id', 'bbox', etc.
            frame_number: Current video frame index
            fps: Video frames per second

        Returns:
            Tuple of (telemetry, grounded_objects_list)
        """
        telemetry = self.srt_parser.get_telemetry_for_frame(frame_number, fps=fps)
        grounded_objects = []

        for obj in tracked_objects:
            bbox = obj.get("bbox", [0, 0, 0, 0])
            # Project bottom-center footprint to GPS
            lat, lon = self.projector.bbox_to_ground_gps(bbox, telemetry)
            
            # Snap to road network
            heading = obj.get("kinematics", {}).get("heading_degrees")
            snap = self.road_network.snap_point_to_network(lat, lon, heading_deg=heading)

            geo_info = {
                "latitude": round(lat, 7),
                "longitude": round(lon, 7),
                "link_id": snap["link_id"],
                "link_name": snap["link_name"],
                "approach": snap["approach"],
                "direction": snap.get("direction", "Unknown"),
                "lane_id": snap["lane_id"],
                "lane_index": snap["lane_index"],
                "lane_type": snap["lane_type"],
                "lateral_offset_meters": snap["lateral_offset_meters"],
                "distance_to_intersection_m": snap["distance_to_intersection_m"],
            }

            obj_copy = dict(obj)
            obj_copy["geodetic_position"] = geo_info
            grounded_objects.append(obj_copy)

        return (telemetry, grounded_objects)

    def generate_map_native_analytics(
        self,
        tracks: List[Dict[str, Any]],
        od_matrix: Optional[Dict[str, Any]] = None,
        last_frame_number: int = 0,
        fps: float = 30.0,
    ) -> Dict[str, Any]:
        """Generate comprehensive map-native analytics report and GeoJSON layers.

        Args:
            tracks: List of track summary records
            od_matrix: Macroscopic Origin-Destination matrix
            last_frame_number: Final frame index
            fps: Video frame rate

        Returns:
            Dict of complete spatial grounding and map layers
        """
        latest_telemetry = self.srt_parser.get_telemetry_for_frame(last_frame_number, fps=fps)
        flight_summary = self.srt_parser.get_flight_summary()

        # Camera footprint polygon
        camera_footprint = self.projector.compute_camera_view_footprint_geojson(latest_telemetry)

        # Road network lane polygons
        road_network_geojson = self.road_network.generate_road_network_geojson()

        # Per-lane metrics on real geometry
        per_lane_metrics = self.road_network.compute_per_lane_metrics_geojson(tracks)

        # Desire lines over actual road layout
        desire_lines = self.road_network.generate_desire_lines_geojson(od_matrix or {})

        # Queue extents along carriageway
        queue_extents = self.road_network.compute_queue_extents_geojson(tracks)

        # Grounded trajectories summary
        geodetic_tracks_summary = []
        for t in tracks:
            geo = t.get("geodetic_position", {})
            k = t.get("kinematics", {})
            geodetic_tracks_summary.append({
                "track_id": t.get("track_id"),
                "class_label": t.get("class_label"),
                "fine_grained_class": t.get("fine_grained_class"),
                "latitude": geo.get("latitude"),
                "longitude": geo.get("longitude"),
                "link_name": geo.get("link_name"),
                "approach": geo.get("approach"),
                "direction": geo.get("direction"),
                "lane_id": geo.get("lane_id"),
                "lane_index": geo.get("lane_index"),
                "speed_kmh": round(k.get("average_speed_kmh", 0.0), 1),
                "distance_traveled_m": round(k.get("distance_traveled_meters", 0.0), 1),
            })

        return {
            "is_spatially_grounded": True,
            "flight_telemetry": flight_summary,
            "intersection_center": {
                "latitude": round(self.road_network.center_lat, 7),
                "longitude": round(self.road_network.center_lon, 7),
            },
            "camera_footprint_geojson": camera_footprint,
            "road_network_geojson": road_network_geojson,
            "per_lane_metrics_geojson": per_lane_metrics,
            "desire_lines_geojson": desire_lines,
            "queue_extents_geojson": queue_extents,
            "geodetic_tracks": geodetic_tracks_summary,
        }
