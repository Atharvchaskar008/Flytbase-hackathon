"""AERIX — Track Manager

Maintains per-track metadata, trajectory history, fine-grained classification,
and real-unit kinematics in memory.
No database dependency — the traffic pipeline uses this to accumulate
track data during processing, then optionally persists to DB afterward.

Each track record stores:
    - track_id, class_label, fine_grained_class
    - first_seen_frame, last_seen_frame
    - first_seen_timestamp, last_seen_timestamp
    - trajectory (list of per-frame bbox + confidence)
    - confidence_history
    - total_detections
    - kinematics (instantaneous speed km/h, accel m/s², heading, motion status)
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

from ml_pipeline.detection.fine_grained import FineGrainedClassifier
from ml_pipeline.tracking.kinematics import KinematicsCalculator

logger = logging.getLogger("aerix.track_manager")


@dataclass
class TrackRecord:
    """In-memory record for a single tracked object with kinematics and fine-grained classification."""
    track_id: int
    class_label: str
    first_seen_frame: int
    last_seen_frame: int
    first_seen_timestamp: float = 0.0
    last_seen_timestamp: float = 0.0
    total_detections: int = 0
    fine_grained_class: str = ""
    fine_grained_attributes: Dict[str, Any] = field(default_factory=dict)
    trajectory: List[Dict[str, Any]] = field(default_factory=list)
    confidence_history: List[float] = field(default_factory=list)
    kinematics: Dict[str, Any] = field(default_factory=dict)


class TrackManager:
    """Manages per-track metadata, trajectory history, fine-grained subclassification,
    and real-unit kinematics.
    
    Usage:
        manager = TrackManager(pixels_per_meter=15.0)
        # Each frame:
        manager.update(tracked_objects, frame_number, video_fps)
        # After processing:
        summaries = manager.get_all_summaries()
    """
    
    def __init__(
        self,
        max_trajectory_length: int = 0,
        pixels_per_meter: float = 15.0,
        homography_matrix: Optional[np.ndarray] = None,
        sample_rate: int = 1,
    ):
        """Initialize track manager.
        
        Args:
            max_trajectory_length: Max trajectory points to keep per track.
                0 = unlimited (keep all). For long videos, set to e.g. 500
                to limit memory usage.
            pixels_per_meter: Pixels per real-world meter for kinematics calculations.
            homography_matrix: Optional 3x3 ground-plane perspective homography matrix.
            sample_rate: Frame sampling interval step.
        """
        self.tracks: Dict[int, TrackRecord] = {}
        self.max_trajectory_length = max_trajectory_length
        self._completed_track_ids: List[int] = []
        self.sample_rate = max(1, sample_rate)
        self.kinematics_calculator = KinematicsCalculator(
            pixels_per_meter=pixels_per_meter,
            homography_matrix=homography_matrix,
        )
    
    def update(
        self,
        tracked_objects: List[Dict[str, Any]],
        frame_number: int,
        video_fps: int = 30,
        frame_shape: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Update track records with new tracked objects from this frame.
        
        Args:
            tracked_objects: List of tracked object dicts from ByteTrackTracker
            frame_number: Current frame number
            video_fps: Video FPS for timestamp calculation
            frame_shape: Optional (height, width) of video frame
        """
        timestamp = frame_number / video_fps if video_fps > 0 else 0.0
        seen_this_frame = set()
        
        for obj in tracked_objects:
            track_id = obj['track_id']
            seen_this_frame.add(track_id)
            
            bbox = obj['bbox']
            confidence = obj.get('confidence', 0.0)
            class_label = obj.get('class_label', 'unknown')

            # Compute fine-grained subclassification
            fine_info = FineGrainedClassifier.classify(
                class_label=class_label,
                bbox=bbox,
                confidence=confidence,
                frame_shape=frame_shape,
            )
            fine_class = fine_info["fine_grained_class"]
            fine_attrs = fine_info.get("attributes", {})
            
            if track_id not in self.tracks:
                # New track
                record = TrackRecord(
                    track_id=track_id,
                    class_label=class_label,
                    fine_grained_class=fine_class,
                    fine_grained_attributes=fine_attrs,
                    first_seen_frame=frame_number,
                    last_seen_frame=frame_number,
                    first_seen_timestamp=timestamp,
                    last_seen_timestamp=timestamp,
                    total_detections=1,
                    trajectory=[{
                        'frame': frame_number,
                        'timestamp': round(timestamp, 3),
                        'bbox': list(bbox),
                        'confidence': round(confidence, 4),
                    }],
                    confidence_history=[confidence],
                )
                # Compute initial kinematics
                record.kinematics = self.kinematics_calculator.calculate_kinematics(
                    record.trajectory,
                    fps=video_fps,
                    sample_rate=self.sample_rate,
                )
                self.tracks[track_id] = record
            else:
                # Update existing track
                record = self.tracks[track_id]
                record.last_seen_frame = frame_number
                record.last_seen_timestamp = timestamp
                record.total_detections += 1
                record.confidence_history.append(confidence)
                # Refine fine-grained class with latest observation
                record.fine_grained_class = fine_class
                record.fine_grained_attributes = fine_attrs
                
                record.trajectory.append({
                    'frame': frame_number,
                    'timestamp': round(timestamp, 3),
                    'bbox': list(bbox),
                    'confidence': round(confidence, 4),
                })
                
                # Trim trajectory if needed
                if self.max_trajectory_length > 0 and len(record.trajectory) > self.max_trajectory_length:
                    record.trajectory = record.trajectory[-self.max_trajectory_length:]

                # Update real-unit kinematics
                record.kinematics = self.kinematics_calculator.calculate_kinematics(
                    record.trajectory,
                    fps=video_fps,
                    sample_rate=self.sample_rate,
                )

            # Store kinematics back into the tracked_object dict so callers have it immediately
            obj['fine_grained_class'] = fine_class
            obj['kinematics'] = record.kinematics
            obj['current_speed_kmh'] = record.kinematics.get('current_speed_kmh', 0.0)
            obj['current_acceleration_ms2'] = record.kinematics.get('current_acceleration_ms2', 0.0)
    
    def mark_lost(self, lost_track_ids: List[int]) -> None:
        """Mark tracks as completed/lost."""
        for tid in lost_track_ids:
            if tid in self.tracks and tid not in self._completed_track_ids:
                self._completed_track_ids.append(tid)
    
    def get_summary(self, track_id: int) -> Optional[Dict[str, Any]]:
        """Get summary for a specific track."""
        record = self.tracks.get(track_id)
        if record is None:
            return None
        return self._record_to_summary(record)
    
    def get_all_summaries(self) -> List[Dict[str, Any]]:
        """Get summaries for all tracks (active + completed)."""
        return [self._record_to_summary(r) for r in self.tracks.values()]
    
    def get_active_summaries(self, current_frame: int, max_age: int = 30) -> List[Dict[str, Any]]:
        """Get summaries for tracks seen within max_age frames of current_frame."""
        return [
            self._record_to_summary(r)
            for r in self.tracks.values()
            if (current_frame - r.last_seen_frame) <= max_age
        ]
    
    def get_completed_tracks(self) -> List[Dict[str, Any]]:
        """Get summaries for tracks that are no longer active."""
        return [
            self._record_to_summary(self.tracks[tid])
            for tid in self._completed_track_ids
            if tid in self.tracks
        ]
    
    def get_class_counts(self) -> Dict[str, int]:
        """Get count of unique tracks per coarse class."""
        counts: Dict[str, int] = {}
        for record in self.tracks.values():
            counts[record.class_label] = counts.get(record.class_label, 0) + 1
        return counts

    def get_fine_grained_class_counts(self) -> Dict[str, int]:
        """Get count of unique tracks per fine-grained subclass."""
        counts: Dict[str, int] = {}
        for record in self.tracks.values():
            fg_cls = record.fine_grained_class or record.class_label
            counts[fg_cls] = counts.get(fg_cls, 0) + 1
        return counts

    def get_kinematics_summary(self) -> Dict[str, Any]:
        """Compute aggregate fleet kinematics statistics."""
        if not self.tracks:
            return {
                "average_speed_kmh": 0.0,
                "max_speed_kmh": 0.0,
                "speeding_count": 0,
                "stopped_count": 0,
                "active_moving_count": 0,
            }

        all_speeds = []
        max_speeds = []
        stopped_count = 0
        speeding_count = 0

        for r in self.tracks.values():
            k = r.kinematics
            cur_speed = k.get("current_speed_kmh", 0.0)
            avg_speed = k.get("average_speed_kmh", 0.0)
            max_speed = k.get("max_speed_kmh", 0.0)
            status = k.get("motion_status", "Stopped")

            all_speeds.append(avg_speed)
            max_speeds.append(max_speed)
            if status == "Stopped":
                stopped_count += 1
            if cur_speed > 60.0 or max_speed > 60.0:
                speeding_count += 1

        fleet_avg = round(float(sum(all_speeds) / len(all_speeds)), 2) if all_speeds else 0.0
        fleet_max = round(float(max(max_speeds)), 2) if max_speeds else 0.0

        return {
            "average_speed_kmh": fleet_avg,
            "max_speed_kmh": fleet_max,
            "speeding_count": speeding_count,
            "stopped_count": stopped_count,
            "active_moving_count": len(self.tracks) - stopped_count,
        }
    
    def get_trajectory_points(self, track_id: int, last_n: int = 0) -> List[tuple]:
        """Get trajectory center points for drawing trails.
        
        Args:
            track_id: Track ID
            last_n: Number of recent points (0 = all)
            
        Returns:
            List of (center_x, center_y) tuples
        """
        record = self.tracks.get(track_id)
        if record is None:
            return []
        
        traj = record.trajectory
        if last_n > 0:
            traj = traj[-last_n:]
        
        points = []
        for entry in traj:
            bbox = entry['bbox']
            cx = int(bbox[0] + bbox[2] / 2)
            cy = int(bbox[1] + bbox[3] / 2)
            points.append((cx, cy))
        
        return points
    
    def _record_to_summary(self, record: TrackRecord) -> Dict[str, Any]:
        """Convert a TrackRecord to a rich summary dict."""
        avg_conf = (
            sum(record.confidence_history) / len(record.confidence_history)
            if record.confidence_history else 0.0
        )
        duration_frames = record.last_seen_frame - record.first_seen_frame
        
        return {
            'track_id': record.track_id,
            'class_label': record.class_label,
            'fine_grained_class': record.fine_grained_class,
            'fine_grained_attributes': record.fine_grained_attributes,
            'first_seen_frame': record.first_seen_frame,
            'last_seen_frame': record.last_seen_frame,
            'first_seen_timestamp': record.first_seen_timestamp,
            'last_seen_timestamp': record.last_seen_timestamp,
            'duration_frames': duration_frames,
            'total_detections': record.total_detections,
            'avg_confidence': round(avg_conf, 4),
            'kinematics': record.kinematics,
            'trajectory': record.trajectory,
            'confidence_history': record.confidence_history,
        }
    
    def __len__(self) -> int:
        return len(self.tracks)
