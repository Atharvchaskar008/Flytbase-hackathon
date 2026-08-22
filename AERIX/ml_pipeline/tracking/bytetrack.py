"""AERIX — ByteTrack Multi-Object Tracker

Uses the supervision library's ByteTrack implementation for robust
multi-object tracking with:
- Kalman filter motion prediction (handles occlusion)
- Hungarian algorithm matching (handles crossing)
- Two-stage association (recovers low-confidence detections)
- Lost track buffer (preserves IDs through missed detections)

Same interface as the existing Tracker class for drop-in compatibility.
"""

import logging
from typing import List, Dict, Any, Tuple, Set

import numpy as np

logger = logging.getLogger("aerix.bytetrack")

# COCO class ID → label (same as YOLODetector.COCO_ID_TO_TRAFFIC)
_COCO_TRAFFIC_NAMES = {
    0: 'person',
    1: 'bicycle',
    2: 'car',
    3: 'motorcycle',
    5: 'bus',
    7: 'truck',
}


class ByteTrackTracker:
    """ByteTrack-based multi-object tracker for traffic detection.
    
    Configuration notes for traffic from drone video:
        - track_activation_threshold=0.25: low enough to catch partial vehicles
        - lost_track_buffer=30: keep tracks ~3s at 10fps during occlusion
        - minimum_matching_threshold=0.8: high IoU since drone view is stable
        - frame_rate: effective fps after frame sampling
    """
    
    def __init__(
        self,
        track_activation_threshold: float = 0.25,
        lost_track_buffer: int = 30,
        minimum_matching_threshold: float = 0.8,
        frame_rate: int = 10,
    ):
        """Initialize ByteTrack tracker.
        
        Args:
            track_activation_threshold: Min confidence to start a new track
            lost_track_buffer: Frames to keep a lost track before removal
            minimum_matching_threshold: Min IoU for matching detections to tracks
            frame_rate: Effective frame rate (after sampling)
        """
        try:
            import supervision as sv
            self._sv = sv
        except ImportError:
            raise ImportError(
                "supervision package required for ByteTrack. "
                "Install with: pip install supervision"
            )
        
        self.tracker = sv.ByteTrack(
            track_activation_threshold=track_activation_threshold,
            lost_track_buffer=lost_track_buffer,
            minimum_matching_threshold=minimum_matching_threshold,
            frame_rate=frame_rate,
        )
        
        self.active_tracks: Set[int] = set()
        self._previous_tracks: Set[int] = set()
        self._track_class_map: Dict[int, str] = {}  # track_id → class_label
        
        self._config = {
            'track_activation_threshold': track_activation_threshold,
            'lost_track_buffer': lost_track_buffer,
            'minimum_matching_threshold': minimum_matching_threshold,
            'frame_rate': frame_rate,
        }
        
        logger.info(
            "[ByteTrack] Initialized (activation=%.2f, buffer=%d, match=%.2f, fps=%d)",
            track_activation_threshold, lost_track_buffer,
            minimum_matching_threshold, frame_rate,
        )
    
    def update(
        self,
        detections: List[Dict[str, Any]],
        frame_number: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, List[int]]]:
        """Update tracks with new detections.
        
        Same interface as the existing Tracker.update() for compatibility.
        
        Args:
            detections: List of detection dicts with bbox, confidence, class_label, class_id
            frame_number: Current frame number
            
        Returns:
            Tuple of:
                - tracked_objects: List of dicts with track_id, bbox, confidence, class_label, etc.
                - lifecycle: Dict with 'new', 'updated', 'lost' track ID lists
        """
        sv = self._sv
        lifecycle = {'new': [], 'updated': [], 'lost': []}
        
        # Handle empty detections
        if not detections:
            sv_empty = sv.Detections.empty()
            self.tracker.update_with_detections(sv_empty)
            current_tracks: Set[int] = set()
            lifecycle['lost'] = list(self._previous_tracks - current_tracks)
            self._previous_tracks = current_tracks
            self.active_tracks = current_tracks
            return [], lifecycle
        
        # Convert detection dicts → supervision Detections
        xyxy_list = []
        conf_list = []
        cid_list = []
        label_list = []
        
        for det in detections:
            bbox = det['bbox']  # [x, y, w, h]
            x, y, w, h = bbox
            xyxy_list.append([x, y, x + w, y + h])
            conf_list.append(det['confidence'])
            cid_list.append(det.get('class_id', 0))
            label_list.append(det.get('class_label', 'unknown'))
        
        sv_detections = sv.Detections(
            xyxy=np.array(xyxy_list, dtype=np.float32),
            confidence=np.array(conf_list, dtype=np.float32),
            class_id=np.array(cid_list, dtype=np.int32),
        )
        
        # Run ByteTrack — returns Detections with tracker_id populated
        tracked = self.tracker.update_with_detections(sv_detections)
        
        # Build tracked object list
        tracked_objects = []
        current_tracks = set()
        
        if tracked.tracker_id is not None and len(tracked) > 0:
            for i in range(len(tracked)):
                track_id = int(tracked.tracker_id[i])
                current_tracks.add(track_id)
                
                # Convert xyxy back to [x, y, w, h]
                x1, y1, x2, y2 = tracked.xyxy[i]
                bbox = [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
                
                # Resolve class label from class_id
                cid = int(tracked.class_id[i]) if tracked.class_id is not None else 0
                class_label = _COCO_TRAFFIC_NAMES.get(cid, 'unknown')
                
                # Store class for this track (use first-seen class — majority vote later if needed)
                if track_id not in self._track_class_map:
                    self._track_class_map[track_id] = class_label
                
                conf = float(tracked.confidence[i]) if tracked.confidence is not None else 0.0
                
                tracked_objects.append({
                    'track_id': track_id,
                    'bbox': bbox,
                    'confidence': conf,
                    'class_label': self._track_class_map[track_id],
                    'class_id': cid,
                    'frame_number': frame_number,
                    'status': 'new' if track_id not in self._previous_tracks else 'tracked',
                })
        
        # Compute lifecycle
        lifecycle['new'] = list(current_tracks - self._previous_tracks)
        lifecycle['updated'] = list(current_tracks & self._previous_tracks)
        lifecycle['lost'] = list(self._previous_tracks - current_tracks)
        
        self._previous_tracks = current_tracks.copy()
        self.active_tracks = current_tracks.copy()
        
        return tracked_objects, lifecycle
    
    def get_active_tracks(self) -> List[int]:
        """Get list of currently active track IDs."""
        return list(self.active_tracks)
    
    def get_config(self) -> Dict[str, Any]:
        """Return the tracker configuration for reporting."""
        return dict(self._config)
