"""AERIX — Kinematics Engine

Calculates real-world kinematics for tracked objects:
- Per-object instantaneous & smoothed velocity (m/s and km/h)
- Per-object instantaneous & smoothed acceleration (m/s²)
- Heading angle (degrees) & cardinal direction (N, NE, E, SE, S, SW, W, NW)
- Dynamic motion status: Stopped, Cruising, Accelerating, Braking

Supports both linear pixel-to-meter scaling and homography transformation
for perspective aerial drone views.
"""

import math
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


class KinematicsCalculator:
    """Calculates physical kinematics (velocity, acceleration, heading) in real-world metric units."""

    def __init__(
        self,
        pixels_per_meter: float = 15.0,
        homography_matrix: Optional[np.ndarray] = None,
        smoothing_alpha: float = 0.6,
        stopped_speed_threshold_kmh: float = 2.0,
    ):
        """Initialize KinematicsCalculator.

        Args:
            pixels_per_meter: Pixels per real-world meter (linear approximation).
            homography_matrix: Optional 3x3 homography matrix mapping pixel (x, y, 1) -> metric (X, Y, 1).
            smoothing_alpha: Exponential moving average factor (0.0 to 1.0) for velocity smoothing.
            stopped_speed_threshold_kmh: Speeds below this are considered stopped/stationary.
        """
        self.pixels_per_meter = max(0.001, float(pixels_per_meter))
        self.homography_matrix = homography_matrix
        self.smoothing_alpha = float(smoothing_alpha)
        self.stopped_speed_threshold_kmh = float(stopped_speed_threshold_kmh)

    def pixel_to_metric(self, px: float, py: float) -> Tuple[float, float]:
        """Convert pixel coordinates to real-world metric coordinates (meters)."""
        if self.homography_matrix is not None:
            pt = np.array([px, py, 1.0], dtype=np.float64)
            transformed = np.dot(self.homography_matrix, pt)
            if abs(transformed[2]) > 1e-6:
                return float(transformed[0] / transformed[2]), float(transformed[1] / transformed[2])

        # Default linear scaling
        return float(px / self.pixels_per_meter), float(py / self.pixels_per_meter)

    def calculate_kinematics(
        self,
        trajectory: List[Dict[str, Any]],
        fps: float = 30.0,
        sample_rate: int = 1,
    ) -> Dict[str, Any]:
        """Compute full kinematic profile from a trajectory history.

        Args:
            trajectory: List of trajectory points [{'frame': int, 'timestamp': float, 'bbox': [x, y, w, h]}, ...]
            fps: Video frame rate
            sample_rate: Frame sampling step

        Returns:
            Dict containing:
                - current_speed_ms: float (m/s)
                - current_speed_kmh: float (km/h)
                - average_speed_kmh: float (km/h)
                - max_speed_kmh: float (km/h)
                - current_acceleration_ms2: float (m/s²)
                - heading_degrees: float (0 - 360)
                - cardinal_direction: str ('N', 'NE', 'E', etc.)
                - motion_status: str ('Stopped', 'Cruising', 'Accelerating', 'Braking')
                - velocity_vector_ms: [vx, vy]
                - distance_traveled_meters: float
        """
        if not trajectory or len(trajectory) < 2:
            return self._empty_kinematics()

        # Calculate time step delta
        # If timestamps exist in trajectory, use them; otherwise use frame count and fps
        metric_positions = []
        timestamps = []

        for p in trajectory:
            bbox = p['bbox']
            # Center of the base of the vehicle (contact point on road)
            cx = bbox[0] + (bbox[2] / 2.0)
            cy = bbox[1] + (bbox[3] / 2.0)
            mx, my = self.pixel_to_metric(cx, cy)
            metric_positions.append((mx, my))

            if 'timestamp' in p and p['timestamp'] is not None and p['timestamp'] > 0:
                timestamps.append(p['timestamp'])
            else:
                frame_idx = p.get('frame', 0)
                timestamps.append(frame_idx / max(1.0, fps))

        speeds_ms: List[float] = []
        velocity_vectors: List[Tuple[float, float]] = []
        smoothed_speeds_ms: List[float] = []
        accelerations_ms2: List[float] = []
        total_distance = 0.0

        for i in range(1, len(metric_positions)):
            dt = timestamps[i] - timestamps[i - 1]
            if dt <= 0:
                dt = (sample_rate / max(1.0, fps))

            dx = metric_positions[i][0] - metric_positions[i - 1][0]
            dy = metric_positions[i][1] - metric_positions[i - 1][1]
            step_distance = math.sqrt(dx * dx + dy * dy)
            total_distance += step_distance

            # Raw instantaneous velocity
            vx = dx / dt
            vy = dy / dt
            v_raw = step_distance / dt

            # Velocity smoothing using EMA
            if smoothed_speeds_ms:
                prev_smooth = smoothed_speeds_ms[-1]
                v_smooth = (self.smoothing_alpha * v_raw) + ((1.0 - self.smoothing_alpha) * prev_smooth)
            else:
                v_smooth = v_raw

            speeds_ms.append(v_raw)
            smoothed_speeds_ms.append(v_smooth)
            velocity_vectors.append((vx, vy))

            # Acceleration: rate of change of speed
            if len(smoothed_speeds_ms) >= 2:
                dv = smoothed_speeds_ms[-1] - smoothed_speeds_ms[-2]
                accel = dv / dt
                # Apply gentle clamping to avoid single-frame noise spikes (> 15 m/s² is physical limit for normal vehicles)
                accel = max(-15.0, min(15.0, accel))
                accelerations_ms2.append(accel)
            else:
                accelerations_ms2.append(0.0)

        current_v_ms = smoothed_speeds_ms[-1] if smoothed_speeds_ms else 0.0
        current_v_kmh = current_v_ms * 3.6
        avg_v_kmh = (sum(smoothed_speeds_ms) / len(smoothed_speeds_ms) * 3.6) if smoothed_speeds_ms else 0.0
        max_v_kmh = (max(smoothed_speeds_ms) * 3.6) if smoothed_speeds_ms else 0.0

        current_accel_ms2 = accelerations_ms2[-1] if accelerations_ms2 else 0.0
        current_vx, current_vy = velocity_vectors[-1] if velocity_vectors else (0.0, 0.0)

        # Calculate heading angle
        heading_deg = (math.degrees(math.atan2(current_vy, current_vx)) + 360) % 360
        cardinal = self._heading_to_cardinal(heading_deg)

        # Motion status
        if current_v_kmh < self.stopped_speed_threshold_kmh:
            status = "Stopped"
            current_v_kmh = 0.0
            current_v_ms = 0.0
        elif current_accel_ms2 > 0.5:
            status = "Accelerating"
        elif current_accel_ms2 < -0.5:
            status = "Braking"
        else:
            status = "Cruising"

        return {
            "current_speed_ms": round(float(current_v_ms), 2),
            "current_speed_kmh": round(float(current_v_kmh), 2),
            "average_speed_kmh": round(float(avg_v_kmh), 2),
            "max_speed_kmh": round(float(max_v_kmh), 2),
            "current_acceleration_ms2": round(float(current_accel_ms2), 2),
            "heading_degrees": round(float(heading_deg), 1),
            "cardinal_direction": cardinal,
            "motion_status": status,
            "velocity_vector_ms": [round(float(current_vx), 2), round(float(current_vy), 2)],
            "distance_traveled_meters": round(float(total_distance), 2),
        }

    @staticmethod
    def _heading_to_cardinal(deg: float) -> str:
        """Convert degree heading to 8-point compass cardinal direction."""
        directions = ["E", "SE", "S", "SW", "W", "NW", "N", "NE"]
        idx = int(((deg + 22.5) % 360) / 45.0)
        return directions[idx]

    @staticmethod
    def _empty_kinematics() -> Dict[str, Any]:
        """Return empty/zero kinematics structure for newly initialized tracks."""
        return {
            "current_speed_ms": 0.0,
            "current_speed_kmh": 0.0,
            "average_speed_kmh": 0.0,
            "max_speed_kmh": 0.0,
            "current_acceleration_ms2": 0.0,
            "heading_degrees": 0.0,
            "cardinal_direction": "N",
            "motion_status": "Stopped",
            "velocity_vector_ms": [0.0, 0.0],
            "distance_traveled_meters": 0.0,
        }
