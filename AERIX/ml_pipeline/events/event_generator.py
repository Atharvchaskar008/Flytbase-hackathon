"""Event Generator - Generates searchable events from tracked objects

Phase 7 Implementation:
- Convert tracking into searchable events
- Instead of: Frame 101, Person, Track 4
- Generate: Object Detected → Track Started → Track Updated → Track Ended
- Store with timestamps for searching
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta


class EventGenerator:
    """Generates searchable lifecycle events based on tracked object behavior"""
    
    def __init__(self, video_fps: int = 30):
        """
        Initialize event generator
        
        Args:
            video_fps: Video FPS for timestamp calculation
        """
        self.event_count = 0
        self.video_fps = video_fps
        self.track_states = {}  # track_id -> last_state
        self.video_start_time = datetime.now()  # Base timestamp
        
        print(f"[EventGenerator] Initialized (FPS: {video_fps})")
    
    def generate_events(
        self, 
        tracked_objects: List[Dict[str, Any]], 
        lifecycle: Dict[str, List[int]],
        frame_number: int
    ) -> List[Dict[str, Any]]:
        """
        Generate searchable lifecycle events (Phase 7)
        
        Args:
            tracked_objects: List of tracked objects in current frame
            lifecycle: Track lifecycle info {'new': [], 'updated': [], 'lost': []}
            frame_number: Current frame number
            
        Returns:
            List of generated events with timestamps
            
        Event Types:
            - object_detected: Initial detection
            - track_started: New track created
            - track_updated: Track continues
            - track_ended: Track lost
        """
        events = []
        timestamp = self._calculate_timestamp(frame_number)
        
        # Phase 7: Generate lifecycle events
        
        # 1. Track Started Events
        for track_id in lifecycle.get('new', []):
            # Find the tracked object
            track_obj = next((obj for obj in tracked_objects if obj['track_id'] == track_id), None)
            if track_obj:
                # Object Detected event
                events.append({
                    'event_type': 'object_detected',
                    'track_id': track_id,
                    'frame_number': frame_number,
                    'confidence': track_obj['confidence'],
                    'timestamp': timestamp,
                    'metadata': {
                        'class_label': track_obj['class_label'],
                        'bbox': track_obj['bbox']
                    }
                })
                
                # Track Started event
                events.append({
                    'event_type': 'track_started',
                    'track_id': track_id,
                    'frame_number': frame_number,
                    'confidence': track_obj['confidence'],
                    'timestamp': timestamp,
                    'metadata': {
                        'class_label': track_obj['class_label'],
                        'initial_bbox': track_obj['bbox']
                    }
                })
                
                # Store the starting frame number for duration calculation
                self.track_states[track_id] = frame_number
                self.event_count += 2
        
        # 2. Track Updated Events
        for track_id in lifecycle.get('updated', []):
            track_obj = next((obj for obj in tracked_objects if obj['track_id'] == track_id), None)
            if track_obj:
                events.append({
                    'event_type': 'track_updated',
                    'track_id': track_id,
                    'frame_number': frame_number,
                    'confidence': track_obj['confidence'],
                    'timestamp': timestamp,
                    'metadata': {
                        'class_label': track_obj['class_label'],
                        'bbox': track_obj['bbox']
                    }
                })
                self.event_count += 1
        
        # 3. Track Ended Events
        for track_id in lifecycle.get('lost', []):
            start_frame = self.track_states.get(track_id, frame_number)
            duration = frame_number - start_frame
            
            events.append({
                'event_type': 'track_ended',
                'track_id': track_id,
                'frame_number': frame_number,
                'confidence': 0.0,
                'timestamp': timestamp,
                'metadata': {
                    'reason': 'lost',
                    'duration_frames': duration,
                    'start_frame': start_frame
                }
            })
            
            if track_id in self.track_states:
                del self.track_states[track_id]
            
            self.event_count += 1
        
        return events
    
    def _calculate_timestamp(self, frame_number: int) -> datetime:
        """
        Calculate timestamp for frame
        
        Args:
            frame_number: Current frame number
            
        Returns:
            Calculated timestamp
        """
        # Calculate seconds from frame number
        seconds = frame_number / self.video_fps
        return self.video_start_time + timedelta(seconds=seconds)
    
    def get_event_count(self) -> int:
        """Get total number of events generated"""
        return self.event_count
    
    def get_event_summary(self) -> Dict[str, int]:
        """Get summary of active tracks"""
        return {
            'active_tracks': len(self.track_states),
            'total_events': self.event_count
        }
