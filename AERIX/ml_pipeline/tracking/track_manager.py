"""AERIX — Track Manager

Maintains per-track metadata and trajectory history in memory.
No database dependency — the traffic pipeline uses this to accumulate
track data during processing, then optionally persists to DB afterward.

Each track record stores:
    - track_id, class_label
    - first_seen_frame, last_seen_frame
    - first_seen_timestamp, last_seen_timestamp
    - trajectory (list of per-frame bbox + confidence)
    - confidence_history
    - total_detections
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("aerix.track_manager")


@dataclass
class TrackRecord:
    """In-memory record for a single tracked object."""
    track_id: int
    class_label: str
    first_seen_frame: int
    last_seen_frame: int
    first_seen_timestamp: float = 0.0
    last_seen_timestamp: float = 0.0
    total_detections: int = 0
    trajectory: List[Dict[str, Any]] = field(default_factory=list)
    confidence_history: List[float] = field(default_factory=list)


class TrackManager:
    """Manages per-track metadata and trajectory history.
    
    Usage:
        manager = TrackManager()
        # Each frame:
        manager.update(tracked_objects, frame_number, video_fps)
        # After processing:
        summaries = manager.get_all_summaries()
    """
    
    def __init__(self, max_trajectory_length: int = 0):
        """Initialize track manager.
        
        Args:
            max_trajectory_length: Max trajectory points to keep per track.
                0 = unlimited (keep all). For long videos, set to e.g. 500
                to limit memory usage.
        """
        self.tracks: Dict[int, TrackRecord] = {}
        self.max_trajectory_length = max_trajectory_length
        self._completed_track_ids: List[int] = []
    
    def update(
        self,
        tracked_objects: List[Dict[str, Any]],
        frame_number: int,
        video_fps: int = 30,
    ) -> None:
        """Update track records with new tracked objects from this frame.
        
        Args:
            tracked_objects: List of tracked object dicts from ByteTrackTracker
            frame_number: Current frame number
            video_fps: Video FPS for timestamp calculation
        """
        timestamp = frame_number / video_fps if video_fps > 0 else 0.0
        seen_this_frame = set()
        
        for obj in tracked_objects:
            track_id = obj['track_id']
            seen_this_frame.add(track_id)
            
            bbox = obj['bbox']
            confidence = obj.get('confidence', 0.0)
            class_label = obj.get('class_label', 'unknown')
            
            if track_id not in self.tracks:
                # New track
                self.tracks[track_id] = TrackRecord(
                    track_id=track_id,
                    class_label=class_label,
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
            else:
                # Update existing track
                record = self.tracks[track_id]
                record.last_seen_frame = frame_number
                record.last_seen_timestamp = timestamp
                record.total_detections += 1
                record.confidence_history.append(confidence)
                
                record.trajectory.append({
                    'frame': frame_number,
                    'timestamp': round(timestamp, 3),
                    'bbox': list(bbox),
                    'confidence': round(confidence, 4),
                })
                
                # Trim trajectory if needed
                if self.max_trajectory_length > 0 and len(record.trajectory) > self.max_trajectory_length:
                    record.trajectory = record.trajectory[-self.max_trajectory_length:]
    
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
        """Get count of unique tracks per class."""
        counts: Dict[str, int] = {}
        for record in self.tracks.values():
            counts[record.class_label] = counts.get(record.class_label, 0) + 1
        return counts
    
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
        """Convert a TrackRecord to a summary dict."""
        avg_conf = (
            sum(record.confidence_history) / len(record.confidence_history)
            if record.confidence_history else 0.0
        )
        duration_frames = record.last_seen_frame - record.first_seen_frame
        
        return {
            'track_id': record.track_id,
            'class_label': record.class_label,
            'first_seen_frame': record.first_seen_frame,
            'last_seen_frame': record.last_seen_frame,
            'first_seen_timestamp': record.first_seen_timestamp,
            'last_seen_timestamp': record.last_seen_timestamp,
            'duration_frames': duration_frames,
            'total_detections': record.total_detections,
            'avg_confidence': round(avg_conf, 4),
            'trajectory': record.trajectory,
            'confidence_history': record.confidence_history,
        }
    
    def __len__(self) -> int:
        return len(self.tracks)
