"""Tracker - Multi-object tracking for maintaining identity across frames

Phase 6 Implementation:
- Input: Bounding Boxes
- Output: Track ID 1, Track ID 2, Track ID 3
- Same person has one ID across frames
- Store: track_id, frame_number, label, confidence
"""

from typing import List, Dict, Any, Tuple
import uuid
import numpy as np


class Tracker:
    """Multi-object tracker for maintaining object identities across frames"""
    
    def __init__(self, iou_threshold: float = 0.3, max_age: int = 30):
        """
        Initialize tracker
        
        Args:
            iou_threshold: Minimum IoU for matching (default: 0.3)
            max_age: Maximum frames to keep lost tracks (default: 30)
        """
        self.tracks = {}  # track_id -> track_info
        self.next_track_id = 1
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.active_tracks = set()  # Currently active track IDs
        
        print(f"[Tracker] Initialized (IoU threshold: {iou_threshold}, Max age: {max_age})")
    
    def update(self, detections: List[Dict[str, Any]], frame_number: int) -> Tuple[List[Dict[str, Any]], Dict[str, List[int]]]:
        """
        Update tracks with new detections (Phase 6)
        
        Args:
            detections: List of detections from current frame
            frame_number: Current frame number
            
        Returns:
            Tuple of:
                - List of tracked objects with persistent track IDs
                - Dictionary of lifecycle events: {'new': [], 'updated': [], 'lost': []}
        """
        tracked_objects = []
        lifecycle = {'new': [], 'updated': [], 'lost': []}
        
        if not detections:
            # Mark tracks as potentially lost
            self._age_tracks(frame_number, lifecycle)
            return tracked_objects, lifecycle
        
        # Match detections to existing tracks
        matched_tracks, unmatched_detections = self._match_detections(detections, frame_number)
        
        # Update matched tracks
        for track_id, detection in matched_tracks:
            tracked_obj = {
                'track_id': track_id,
                'bbox': detection['bbox'],
                'confidence': detection['confidence'],
                'class_label': detection['class_label'],
                'frame_number': frame_number,
                'status': 'tracked'
            }
            tracked_objects.append(tracked_obj)
            
            # Update track info
            self.tracks[track_id]['last_seen'] = frame_number
            self.tracks[track_id]['last_bbox'] = detection['bbox']
            self.tracks[track_id]['age'] = 0
            self.active_tracks.add(track_id)
            lifecycle['updated'].append(track_id)
        
        # Create new tracks for unmatched detections
        for detection in unmatched_detections:
            track_id = self.next_track_id
            self.next_track_id += 1
            
            tracked_obj = {
                'track_id': track_id,
                'bbox': detection['bbox'],
                'confidence': detection['confidence'],
                'class_label': detection['class_label'],
                'frame_number': frame_number,
                'status': 'new'
            }
            tracked_objects.append(tracked_obj)
            
            # Create new track
            self.tracks[track_id] = {
                'first_seen': frame_number,
                'last_seen': frame_number,
                'last_bbox': detection['bbox'],
                'global_id': str(uuid.uuid4())[:8],
                'age': 0,
                'class_label': detection['class_label']
            }
            self.active_tracks.add(track_id)
            lifecycle['new'].append(track_id)
        
        # Age tracks that weren't matched
        self._age_tracks(frame_number, lifecycle)
        
        return tracked_objects, lifecycle
    
    def _match_detections(
        self, 
        detections: List[Dict[str, Any]], 
        frame_number: int
    ) -> Tuple[List[Tuple[int, Dict]], List[Dict]]:
        """
        Match current detections to existing tracks using IoU
        
        Returns:
            Tuple of (matched_tracks, unmatched_detections)
        """
        if not self.active_tracks:
            return [], detections
        
        matched_tracks = []
        unmatched_detections = []
        
        # Simple greedy matching based on IoU
        # In production, use Hungarian algorithm or more sophisticated matching
        used_detections = set()
        
        for track_id in list(self.active_tracks):
            track_info = self.tracks[track_id]
            last_bbox = track_info.get('last_bbox')
            
            if not last_bbox:
                continue
            
            best_iou = 0
            best_detection_idx = -1
            
            for idx, detection in enumerate(detections):
                if idx in used_detections:
                    continue
                
                iou = self._calculate_iou(last_bbox, detection['bbox'])
                if iou > best_iou and iou >= self.iou_threshold:
                    best_iou = iou
                    best_detection_idx = idx
            
            if best_detection_idx >= 0:
                matched_tracks.append((track_id, detections[best_detection_idx]))
                used_detections.add(best_detection_idx)
        
        # Unmatched detections become new tracks
        for idx, detection in enumerate(detections):
            if idx not in used_detections:
                unmatched_detections.append(detection)
        
        return matched_tracks, unmatched_detections
    
    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """
        Calculate Intersection over Union (IoU) between two bounding boxes
        
        Args:
            bbox1, bbox2: [x, y, width, height]
            
        Returns:
            IoU score (0-1)
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Calculate intersection
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _age_tracks(self, frame_number: int, lifecycle: Dict[str, List[int]]) -> None:
        """Age tracks that weren't updated and remove old ones"""
        tracks_to_remove = []
        
        for track_id in list(self.active_tracks):
            track_info = self.tracks[track_id]
            if track_info['last_seen'] < frame_number:
                track_info['age'] += 1
                
                if track_info['age'] > self.max_age:
                    tracks_to_remove.append(track_id)
                    lifecycle['lost'].append(track_id)
        
        # Remove lost tracks
        for track_id in tracks_to_remove:
            self.active_tracks.discard(track_id)
    
    def get_active_tracks(self) -> List[int]:
        """Get list of currently active track IDs"""
        return list(self.active_tracks)
    
    def get_track_info(self, track_id: int) -> Dict[str, Any]:
        """Get information about a specific track"""
        return self.tracks.get(track_id, {})
