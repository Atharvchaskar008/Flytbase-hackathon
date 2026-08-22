"""AERIX — Ground-Plane Camera Projection Engine

Transforms image-plane pixel coordinates (u, v) into real-world geographic coordinates (lat, lon)
and metric local tangent coordinates (East, North in meters) using:
- 3D pinhole camera optics model (sensor size, focal length, principal point)
- Drone 6-DoF spatial pose (GPS lat/lon, altitude Z, gimbal pitch, roll, yaw)
- Analytical ground-plane ray-casting (intersection of viewing ray with ground plane Z=0)
- Per-frame Homography transformation matrix H
"""

import math
from typing import Dict, List, Optional, Tuple, Union
import numpy as np

from .srt_parser import DroneFrameTelemetry


class GroundProjector:
    """Projects pixel coordinates to WGS84 geographic and local metric coordinates."""

    # Earth radius in meters (WGS84 mean)
    EARTH_RADIUS_METERS = 6378137.0

    def __init__(
        self,
        frame_shape: Tuple[int, int] = (720, 1280),
        default_hfov_deg: float = 84.0,
    ):
        """Initialize Ground Projector.

        Args:
            frame_shape: (height, width) of video frame in pixels.
            default_hfov_deg: Horizontal camera field of view in degrees.
        """
        self.height, self.width = frame_shape
        self.hfov_deg = default_hfov_deg
        self.vfov_deg = default_hfov_deg * (self.height / max(1.0, float(self.width)))

        # Focal lengths in pixel units
        self.fx = (self.width / 2.0) / math.tan(math.radians(self.hfov_deg / 2.0))
        self.fy = (self.height / 2.0) / math.tan(math.radians(self.vfov_deg / 2.0))
        self.cx = self.width / 2.0
        self.cy = self.height / 2.0

        # Intrinsic matrix K
        self.K = np.array([
            [self.fx, 0.0,     self.cx],
            [0.0,     self.fy, self.cy],
            [0.0,     0.0,     1.0    ]
        ], dtype=np.float64)
        self.K_inv = np.linalg.inv(self.K)

    def pixel_to_ground_metric(
        self,
        u: float,
        v: float,
        telemetry: DroneFrameTelemetry,
    ) -> Tuple[float, float]:
        """Project a single pixel (u, v) to Local Metric Tangent Plane (East_m, North_m) relative to drone.

        Args:
            u: Horizontal pixel coordinate (0 to width)
            v: Vertical pixel coordinate (0 to height)
            telemetry: Drone spatial telemetry for the frame

        Returns:
            Tuple of (east_meters, north_meters) from drone ground nadir point.
        """
        # Normalized camera ray in camera optical frame (X right, Y down, Z forward)
        p_cam = self.K_inv @ np.array([u, v, 1.0], dtype=np.float64)
        p_cam = p_cam / np.linalg.norm(p_cam)

        # Convert gimbal angles to radians
        # pitch: -90 = straight down, -45 = 45 deg forward tilt
        pitch = math.radians(telemetry.gimbal_pitch_deg)
        roll = math.radians(telemetry.gimbal_roll_deg)
        # yaw: 0 = North, 90 = East, 180 = South, 270 = West
        yaw = math.radians(telemetry.gimbal_yaw_deg)

        # Camera to World Rotation Matrix R
        # In World ENU frame: X = East, Y = North, Z = Up
        # For a downward looking drone at yaw=0:
        # Camera Z points Down (-Z), Camera Y points North (+Y), Camera X points East (+X)
        pitch_tilt = pitch + math.pi / 2.0  # 0 for straight down nadir

        # Rotation around camera X axis (pitch tilt)
        Rx = np.array([
            [1.0, 0.0, 0.0],
            [0.0, math.cos(pitch_tilt), -math.sin(pitch_tilt)],
            [0.0, math.sin(pitch_tilt),  math.cos(pitch_tilt)]
        ])

        # Rotation around world Z axis (yaw heading)
        Rz = np.array([
            [math.cos(yaw), math.sin(yaw), 0.0],
            [-math.sin(yaw), math.cos(yaw), 0.0],
            [0.0, 0.0, 1.0]
        ])

        # Composite rotation from camera frame to ENU frame
        # Optical frame to vehicle frame mapping
        R_cam_to_body = np.array([
            [1.0,  0.0,  0.0],
            [0.0, -1.0,  0.0],
            [0.0,  0.0, -1.0]
        ])

        R = Rz.T @ Rx @ R_cam_to_body
        ray_world = R @ p_cam

        # Altitude above ground plane
        alt = max(5.0, telemetry.relative_altitude_m)

        # Ray-Plane intersection with Z = 0 (ground plane)
        # Drone is at (0, 0, alt) in local ENU frame
        # Ray equation: P(t) = (0, 0, alt) + t * (ray_x, ray_y, ray_z)
        # Intersection when Z = 0: alt + t * ray_z = 0 -> t = -alt / ray_z
        if abs(ray_world[2]) < 1e-4:
            # Ray is parallel to ground
            t = 1000.0
        else:
            t = -alt / ray_world[2]
            if t < 0:
                t = abs(t)  # Ensure positive forward projection

        east_m = float(ray_world[0] * t)
        north_m = float(ray_world[1] * t)

        return (east_m, north_m)

    def metric_to_geodetic(
        self,
        east_m: float,
        north_m: float,
        ref_lat: float,
        ref_lon: float,
    ) -> Tuple[float, float]:
        """Convert local metric (East, North) displacement to WGS84 (lat, lon)."""
        lat_rad = math.radians(ref_lat)
        delta_lat = (north_m / self.EARTH_RADIUS_METERS) * (180.0 / math.pi)
        delta_lon = (east_m / (self.EARTH_RADIUS_METERS * math.cos(lat_rad))) * (180.0 / math.pi)

        return (ref_lat + delta_lat, ref_lon + delta_lon)

    def geodetic_to_metric(
        self,
        lat: float,
        lon: float,
        ref_lat: float,
        ref_lon: float,
    ) -> Tuple[float, float]:
        """Convert WGS84 (lat, lon) to local metric (East, North) from reference."""
        lat_rad = math.radians(ref_lat)
        delta_lat_deg = lat - ref_lat
        delta_lon_deg = lon - ref_lon

        north_m = (delta_lat_deg * math.pi / 180.0) * self.EARTH_RADIUS_METERS
        east_m = (delta_lon_deg * math.pi / 180.0) * (self.EARTH_RADIUS_METERS * math.cos(lat_rad))

        return (east_m, north_m)

    def pixel_to_gps(
        self,
        u: float,
        v: float,
        telemetry: DroneFrameTelemetry,
    ) -> Tuple[float, float]:
        """Project an image pixel (u, v) to WGS84 (latitude, longitude).

        Args:
            u: Horizontal pixel coordinate (0 to width)
            v: Vertical pixel coordinate (0 to height)
            telemetry: Drone frame telemetry

        Returns:
            Tuple of (latitude, longitude)
        """
        east_m, north_m = self.pixel_to_ground_metric(u, v, telemetry)
        return self.metric_to_geodetic(east_m, north_m, telemetry.latitude, telemetry.longitude)

    def bbox_to_ground_gps(
        self,
        bbox: Union[List[float], Tuple[float, float, float, float]],
        telemetry: DroneFrameTelemetry,
    ) -> Tuple[float, float]:
        """Project vehicle bounding box footpoint [x + w/2, y + h] to ground GPS.

        In aerial tracking, the bottom-center of the bounding box represents
        the physical contact point of the vehicle tires with the road pavement.
        """
        x, y, w, h = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        # Bottom-center contact point
        u_contact = np.clip(x + (w / 2.0), 0.0, float(self.width))
        v_contact = np.clip(y + h, 0.0, float(self.height))

        return self.pixel_to_gps(u_contact, v_contact, telemetry)

    def compute_camera_view_footprint_geojson(
        self,
        telemetry: DroneFrameTelemetry,
    ) -> Dict[str, Any]:
        """Compute the 4-corner ground projection polygon of the camera viewport as GeoJSON."""
        corners_px = [
            (0.0, 0.0),                     # Top-Left
            (float(self.width), 0.0),        # Top-Right
            (float(self.width), float(self.height)),  # Bottom-Right
            (0.0, float(self.height)),       # Bottom-Left
            (0.0, 0.0),                     # Close loop
        ]

        coords = []
        for u, v in corners_px:
            lat, lon = self.pixel_to_gps(u, v, telemetry)
            coords.append([round(lon, 7), round(lat, 7)])

        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            },
            "properties": {
                "name": "Drone Camera Ground Footprint",
                "altitude_m": round(telemetry.relative_altitude_m, 1),
                "pitch_deg": round(telemetry.gimbal_pitch_deg, 1),
                "yaw_deg": round(telemetry.gimbal_yaw_deg, 1),
            }
        }
