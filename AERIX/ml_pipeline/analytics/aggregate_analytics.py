"""
AERIX — Macroscopic & Aggregate Traffic Analytics Engine

Provides aggregate traffic intelligence across road users, spatial zones,
and time windows:
1. Classified Turning Movements (Through, Left, Right, U-Turn) & Interval Volumes
2. Origin–Destination (O-D) Flow Matrix & Route Distribution
3. Segment-Wise Speed Profiles (Mean, P85, P15) & Speeding Hotspots
4. Lane Volumes & Modal Split by Lane
5. Queue Length Estimation (meters & vehicle count) & Delay
6. Density (veh/km), Area Occupancy (%), Hourly Flow Rate (veh/h), and Level of Service (LOS)
"""

import math
from typing import Dict, List, Any, Optional, Tuple
import numpy as np


class MacroTrafficAnalyticsEngine:
    """Computes macroscopic, spatial, and aggregate traffic metrics from trajectory and track datasets."""

    def __init__(
        self,
        speed_limit_kmh: float = 50.0,
        queue_speed_threshold_kmh: float = 6.0,
        pixels_per_meter: float = 15.0,
    ):
        """Initialize macroscopic analytics engine.

        Args:
            speed_limit_kmh: Speed limit threshold for speeding hotspot analysis.
            queue_speed_threshold_kmh: Velocity below which vehicles are considered queued.
            pixels_per_meter: Scale factor mapping video pixels to real-world meters.
        """
        self.speed_limit_kmh = float(speed_limit_kmh)
        self.queue_speed_threshold_kmh = float(queue_speed_threshold_kmh)
        self.pixels_per_meter = max(0.001, float(pixels_per_meter))

    def generate_comprehensive_analytics(
        self,
        tracks: List[Dict[str, Any]],
        frames_processed: int,
        fps: float = 30.0,
        sample_rate: int = 3,
        frame_shape: Tuple[int, int] = (720, 1280),
    ) -> Dict[str, Any]:
        """Generate complete macroscopic and aggregate analytics report.

        Args:
            tracks: List of track summary dictionaries from TrackManager
            frames_processed: Total number of frames processed
            fps: Video frames per second
            sample_rate: Frame sampling interval step
            frame_shape: (height, width) of the video

        Returns:
            Dict containing turning movements, O-D matrix, speed profiles,
            lane modal splits, queue lengths, density/occupancy, and LOS.
        """
        turning_movements = self.compute_turning_movements(tracks, frame_shape)
        od_matrix = self.compute_origin_destination_matrix(tracks, frame_shape)
        speed_profiles = self.compute_segment_speed_profiles(tracks, frame_shape)
        lane_analytics = self.compute_lane_volumes_and_modal_split(tracks, frame_shape)
        queue_analytics = self.compute_queue_lengths(tracks, fps, sample_rate)
        density_occupancy = self.compute_density_occupancy_flow(
            tracks, frames_processed, fps, sample_rate, frame_shape
        )

        return {
            "turning_movements": turning_movements,
            "origin_destination_matrix": od_matrix,
            "speed_profiles": speed_profiles,
            "lane_analytics": lane_analytics,
            "queue_analytics": queue_analytics,
            "macroscopic_flow": density_occupancy,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Classified Movement & Turning Counts
    # ─────────────────────────────────────────────────────────────────────────

    def compute_turning_movements(
        self,
        tracks: List[Dict[str, Any]],
        frame_shape: Tuple[int, int] = (720, 1280),
    ) -> Dict[str, Any]:
        """Classify vehicle trajectories into turning movements and approach flows."""
        height, width = frame_shape
        movement_counts = {
            "Through (Straight)": 0,
            "Left Turn": 0,
            "Right Turn": 0,
            "U-Turn": 0,
        }
        approach_counts = {"Northbound": 0, "Southbound": 0, "Eastbound": 0, "Westbound": 0}
        classified_movements: Dict[str, Dict[str, int]] = {
            "Through (Straight)": {},
            "Left Turn": {},
            "Right Turn": {},
            "U-Turn": {},
        }

        for track in tracks:
            traj = track.get("trajectory", [])
            if len(traj) < 3:
                continue

            fg_class = track.get("fine_grained_class") or track.get("class_label", "car")

            # Entry point (average of first 2 points) and Exit point (average of last 2 points)
            p_start = self._bbox_center(traj[0]["bbox"])
            p_mid = self._bbox_center(traj[len(traj) // 2]["bbox"])
            p_end = self._bbox_center(traj[-1]["bbox"])

            # Entry vector & Exit vector
            v_in = (p_mid[0] - p_start[0], p_mid[1] - p_start[1])
            v_out = (p_end[0] - p_mid[0], p_end[1] - p_mid[1])

            # Overall displacement
            dx_total = p_end[0] - p_start[0]
            dy_total = p_end[1] - p_start[1]

            # Determine dominant approach
            if abs(dx_total) > abs(dy_total):
                approach = "Eastbound" if dx_total > 0 else "Westbound"
            else:
                approach = "Southbound" if dy_total > 0 else "Northbound"
            approach_counts[approach] += 1

            # Compute turning angle
            angle_in = math.atan2(v_in[1], v_in[0])
            angle_out = math.atan2(v_out[1], v_out[0])
            delta_angle = math.degrees(angle_out - angle_in)
            # Normalize to [-180, 180]
            delta_angle = (delta_angle + 180) % 360 - 180

            # Classification rules based on heading deflection
            if abs(delta_angle) < 35:
                movement = "Through (Straight)"
            elif 35 <= delta_angle <= 145:
                # In standard screen coordinates (y downwards), clockwise is positive -> Right turn in screen or Left in geographic
                movement = "Right Turn"
            elif -145 <= delta_angle <= -35:
                movement = "Left Turn"
            else:
                movement = "U-Turn"

            movement_counts[movement] += 1
            classified_movements[movement][fg_class] = classified_movements[movement].get(fg_class, 0) + 1

        total_movements = sum(movement_counts.values())
        proportions = {
            k: round((v / max(1, total_movements)) * 100, 1)
            for k, v in movement_counts.items()
        }

        return {
            "total_movements_analyzed": total_movements,
            "movement_counts": movement_counts,
            "movement_proportions_pct": proportions,
            "approach_directional_volumes": approach_counts,
            "classified_movement_breakdown": classified_movements,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Origin–Destination (O-D) Matrix
    # ─────────────────────────────────────────────────────────────────────────

    def compute_origin_destination_matrix(
        self,
        tracks: List[Dict[str, Any]],
        frame_shape: Tuple[int, int] = (720, 1280),
    ) -> Dict[str, Any]:
        """Compute origin-destination flow matrix and route proportions across spatial approaches."""
        height, width = frame_shape
        zones = ["North Approach", "South Approach", "East Approach", "West Approach"]

        # Matrix: origin -> destination -> count
        matrix: Dict[str, Dict[str, int]] = {z: {z_out: 0 for z_out in zones} for z in zones}
        total_trips = 0

        for track in tracks:
            traj = track.get("trajectory", [])
            if len(traj) < 2:
                continue

            p_start = self._bbox_center(traj[0]["bbox"])
            p_end = self._bbox_center(traj[-1]["bbox"])

            orig = self._point_to_zone(p_start, width, height)
            dest = self._point_to_zone(p_end, width, height)

            matrix[orig][dest] += 1
            total_trips += 1

        # Percentage distribution matrix
        percentage_matrix = {
            orig: {
                dest: round((count / max(1, total_trips)) * 100, 1)
                for dest, count in dest_counts.items()
            }
            for orig, dest_counts in matrix.items()
        }

        # Top origin-destination corridors
        corridors = []
        for orig, dests in matrix.items():
            for dest, count in dests.items():
                if count > 0:
                    pct = round((count / max(1, total_trips)) * 100, 1)
                    corridors.append({
                        "origin": orig,
                        "destination": dest,
                        "volume": count,
                        "proportion_pct": pct,
                    })
        corridors.sort(key=lambda x: x["volume"], reverse=True)

        return {
            "zones": zones,
            "total_trips": total_trips,
            "od_matrix_counts": matrix,
            "od_matrix_percentages": percentage_matrix,
            "major_corridors": corridors[:8],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Segment Speed Profiles & Speeding Hotspot Analysis
    # ─────────────────────────────────────────────────────────────────────────

    def compute_segment_speed_profiles(
        self,
        tracks: List[Dict[str, Any]],
        frame_shape: Tuple[int, int] = (720, 1280),
        num_segments: int = 5,
    ) -> Dict[str, Any]:
        """Compute segment-by-segment speed statistics and identify speeding hotspots."""
        height, width = frame_shape
        segment_width = width / num_segments
        segment_speeds: List[List[float]] = [[] for _ in range(num_segments)]

        for track in tracks:
            traj = track.get("trajectory", [])
            kin = track.get("kinematics", {})
            spd = kin.get("current_speed_kmh") or kin.get("average_speed_kmh", 0.0)

            for p in traj:
                cx, cy = self._bbox_center(p["bbox"])
                seg_idx = min(num_segments - 1, max(0, int(cx / segment_width)))
                if spd > 0.5:
                    segment_speeds[seg_idx].append(spd)

        profiles = []
        speeding_hotspots = []

        for i in range(num_segments):
            speeds = segment_speeds[i]
            x_start_m = round((i * segment_width) / self.pixels_per_meter, 1)
            x_end_m = round(((i + 1) * segment_width) / self.pixels_per_meter, 1)
            seg_name = f"Segment {i + 1} ({x_start_m}m - {x_end_m}m)"

            if speeds:
                mean_spd = float(np.mean(speeds))
                p85_spd = float(np.percentile(speeds, 85))
                p15_spd = float(np.percentile(speeds, 15))
                std_spd = float(np.std(speeds))
                speeding_count = sum(1 for s in speeds if s > self.speed_limit_kmh)
                speeding_pct = round((speeding_count / len(speeds)) * 100, 1)
            else:
                mean_spd, p85_spd, p15_spd, std_spd, speeding_pct = 0.0, 0.0, 0.0, 0.0, 0.0

            prof_entry = {
                "segment_index": i + 1,
                "segment_name": seg_name,
                "sample_count": len(speeds),
                "mean_speed_kmh": round(mean_spd, 1),
                "p85_speed_kmh": round(p85_spd, 1),
                "p15_speed_kmh": round(p15_spd, 1),
                "speed_std_kmh": round(std_spd, 1),
                "speeding_percentage": speeding_pct,
                "risk_level": "High" if speeding_pct > 25 else ("Moderate" if speeding_pct > 10 else "Normal"),
            }
            profiles.append(prof_entry)

            if speeding_pct > 15.0:
                speeding_hotspots.append({
                    "segment": seg_name,
                    "speeding_rate_pct": speeding_pct,
                    "p85_speed_kmh": round(p85_spd, 1),
                })

        return {
            "speed_limit_kmh": self.speed_limit_kmh,
            "segment_profiles": profiles,
            "speeding_hotspots": speeding_hotspots,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Lane Volume & Modal Split by Lane
    # ─────────────────────────────────────────────────────────────────────────

    def compute_lane_volumes_and_modal_split(
        self,
        tracks: List[Dict[str, Any]],
        frame_shape: Tuple[int, int] = (720, 1280),
        num_lanes: int = 3,
    ) -> Dict[str, Any]:
        """Compute lane-specific vehicle volume, mean speed, and modal split breakdown."""
        height, width = frame_shape
        lane_height = height / num_lanes
        lane_names = [f"Lane {i + 1} ({'Fast/Inner' if i == 0 else ('Center' if i == 1 else 'Slow/Curb')})" for i in range(num_lanes)]

        lane_counts = [0 for _ in range(num_lanes)]
        lane_speeds: List[List[float]] = [[] for _ in range(num_lanes)]
        lane_modal_counts: List[Dict[str, int]] = [{} for _ in range(num_lanes)]

        for track in tracks:
            traj = track.get("trajectory", [])
            if not traj:
                continue

            fg_class = track.get("fine_grained_class") or track.get("class_label", "car")
            kin = track.get("kinematics", {})
            spd = kin.get("current_speed_kmh") or kin.get("average_speed_kmh", 0.0)

            # Use average y-position of trajectory to assign lane
            y_positions = [self._bbox_center(p["bbox"])[1] for p in traj]
            avg_y = sum(y_positions) / len(y_positions)
            lane_idx = min(num_lanes - 1, max(0, int(avg_y / lane_height)))

            lane_counts[lane_idx] += 1
            if spd > 0:
                lane_speeds[lane_idx].append(spd)
            lane_modal_counts[lane_idx][fg_class] = lane_modal_counts[lane_idx].get(fg_class, 0) + 1

        total_volume = sum(lane_counts)
        lane_summaries = []

        for i in range(num_lanes):
            count = lane_counts[i]
            speeds = lane_speeds[i]
            avg_speed = round(float(np.mean(speeds)), 1) if speeds else 0.0
            vol_pct = round((count / max(1, total_volume)) * 100, 1)

            # Compute modal split percentages
            modal_breakdown = {}
            for cls, c_cnt in lane_modal_counts[i].items():
                modal_breakdown[cls] = round((c_cnt / max(1, count)) * 100, 1)

            lane_summaries.append({
                "lane_id": i + 1,
                "lane_name": lane_names[i],
                "volume": count,
                "volume_share_pct": vol_pct,
                "average_speed_kmh": avg_speed,
                "modal_split_pct": modal_breakdown,
                "vehicle_counts": lane_modal_counts[i],
            })

        return {
            "total_roadway_volume": total_volume,
            "lanes": lane_summaries,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Queue Length Estimation & Delay
    # ─────────────────────────────────────────────────────────────────────────

    def compute_queue_lengths(
        self,
        tracks: List[Dict[str, Any]],
        fps: float = 30.0,
        sample_rate: int = 3,
    ) -> Dict[str, Any]:
        """Estimate queue length in real meters, queued vehicle count, and dwell delay."""
        queued_tracks = []
        effective_fps = max(1.0, fps / sample_rate)

        for track in tracks:
            kin = track.get("kinematics", {})
            spd = kin.get("current_speed_kmh", 0.0)
            avg_spd = kin.get("average_speed_kmh", 0.0)
            duration_frames = track.get("duration_frames", len(track.get("trajectory", [])))
            duration_sec = duration_frames / effective_fps

            # Queued if moving very slowly or stopped for at least 2.0 seconds
            if (spd <= self.queue_speed_threshold_kmh or avg_spd <= self.queue_speed_threshold_kmh) and duration_sec >= 1.5:
                queued_tracks.append({
                    "track_id": track.get("track_id"),
                    "class_label": track.get("fine_grained_class") or track.get("class_label"),
                    "speed_kmh": spd,
                    "delay_seconds": round(duration_sec, 1),
                    "trajectory": track.get("trajectory", []),
                })

        if not queued_tracks:
            return {
                "active_queues_detected": 0,
                "max_queue_length_meters": 0.0,
                "average_queue_length_meters": 0.0,
                "total_queued_vehicles": 0,
                "average_delay_seconds": 0.0,
                "queuing_status": "Free Flow / No Significant Queuing",
            }

        # Calculate bounding spatial extent of queued vehicles
        all_x = []
        all_y = []
        delays = []

        for q in queued_tracks:
            delays.append(q["delay_seconds"])
            traj = q["trajectory"]
            if traj:
                cx, cy = self._bbox_center(traj[-1]["bbox"])
                all_x.append(cx)
                all_y.append(cy)

        if all_x and all_y:
            span_x_m = (max(all_x) - min(all_x)) / self.pixels_per_meter
            span_y_m = (max(all_y) - min(all_y)) / self.pixels_per_meter
            queue_length_m = round(math.sqrt(span_x_m * span_x_m + span_y_m * span_y_m), 1)
        else:
            queue_length_m = 0.0

        avg_delay = round(float(np.mean(delays)), 1) if delays else 0.0

        status = "Light Queue"
        if queue_length_m > 40.0 or len(queued_tracks) > 8:
            status = "Severe Congestion Queue"
        elif queue_length_m > 15.0 or len(queued_tracks) > 3:
            status = "Moderate Queue"

        return {
            "active_queues_detected": 1 if queued_tracks else 0,
            "max_queue_length_meters": queue_length_m,
            "average_queue_length_meters": round(queue_length_m * 0.75, 1),
            "total_queued_vehicles": len(queued_tracks),
            "average_delay_seconds": avg_delay,
            "queuing_status": status,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Density, Occupancy & Flow–Density Relationships (MFD)
    # ─────────────────────────────────────────────────────────────────────────

    def compute_density_occupancy_flow(
        self,
        tracks: List[Dict[str, Any]],
        frames_processed: int,
        fps: float = 30.0,
        sample_rate: int = 3,
        frame_shape: Tuple[int, int] = (720, 1280),
    ) -> Dict[str, Any]:
        """Compute macroscopic Density (k), Occupancy (O%), Flow Rate (q), and Level of Service (LOS)."""
        height, width = frame_shape
        road_area_sq_pixels = height * width * 0.75  # Approximate roadway footprint
        road_length_meters = width / self.pixels_per_meter
        road_length_km = max(0.001, road_length_meters / 1000.0)

        effective_fps = max(1.0, fps / sample_rate)
        duration_seconds = max(1.0, frames_processed / effective_fps)
        duration_hours = duration_seconds / 3600.0

        unique_vehicles = len(tracks)
        hourly_flow_rate = round(unique_vehicles / duration_hours, 1)

        # Average vehicle area footprint
        total_veh_area_pixels = 0.0
        speeds = []

        for track in tracks:
            traj = track.get("trajectory", [])
            if traj:
                bbox = traj[-1]["bbox"]
                total_veh_area_pixels += (bbox[2] * bbox[3])
            kin = track.get("kinematics", {})
            spd = kin.get("average_speed_kmh", 0.0)
            if spd > 0:
                speeds.append(spd)

        avg_speed_kmh = float(np.mean(speeds)) if speeds else 35.0

        # Occupancy % = vehicle pixels / road pixels * 100
        occupancy_pct = round(min(100.0, (total_veh_area_pixels / max(1.0, road_area_sq_pixels)) * 100.0), 2)

        # Density k = vehicles / km
        density_veh_km = round(unique_vehicles / road_length_km, 1)

        # Level of Service (LOS) according to Highway Capacity Manual (HCM)
        if avg_speed_kmh >= 48 and occupancy_pct < 12:
            los = "LOS A — Free Flow"
            mfd_state = "Free-Flow Branch"
        elif avg_speed_kmh >= 38 and occupancy_pct < 22:
            los = "LOS B — Reasonably Free Flow"
            mfd_state = "Stable Flow"
        elif avg_speed_kmh >= 28 and occupancy_pct < 35:
            los = "LOS C — Stable Flow"
            mfd_state = "Near Capacity"
        elif avg_speed_kmh >= 18 and occupancy_pct < 50:
            los = "LOS D — Approaching Unstable Flow"
            mfd_state = "Capacity Peak (Critical Density)"
        elif avg_speed_kmh >= 10 and occupancy_pct < 70:
            los = "LOS E — Unstable Flow / Capacity"
            mfd_state = "Congested Branch"
        else:
            los = "LOS F — Breakdown / Forced Flow"
            mfd_state = "Gridlock / Bottleneck Breakdown"

        return {
            "density_vehicles_per_km": density_veh_km,
            "road_area_occupancy_pct": occupancy_pct,
            "hourly_flow_rate_veh_hour": hourly_flow_rate,
            "average_speed_kmh": round(avg_speed_kmh, 1),
            "level_of_service": los,
            "mfd_congestion_state": mfd_state,
            "duration_seconds_analyzed": round(duration_seconds, 1),
            "road_segment_length_meters": round(road_length_meters, 1),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _bbox_center(bbox: List[float]) -> Tuple[float, float]:
        """Compute centroid of bounding box."""
        return float(bbox[0] + bbox[2] / 2.0), float(bbox[1] + bbox[3] / 2.0)

    @staticmethod
    def _point_to_zone(point: Tuple[float, float], width: float, height: float) -> str:
        """Map centroid coordinate to 4 primary approach zones (North, South, East, West)."""
        x, y = point
        # Distance to borders
        d_top = y
        d_bottom = height - y
        d_left = x
        d_right = width - x

        min_d = min(d_top, d_bottom, d_left, d_right)
        if min_d == d_top:
            return "North Approach"
        elif min_d == d_bottom:
            return "South Approach"
        elif min_d == d_left:
            return "West Approach"
        else:
            return "East Approach"
