"""
Phase 18 - Timeline Intelligence ⭐⭐⭐⭐⭐

Don't just return events. Convert them into a meaningful sequence.

Instead of:
Track 14, Frame 120, Frame 340, Frame 890

Return:
09:31 Entered → 09:32 Walking → 09:34 Near Checkout → 09:36 Exited

This makes the timeline understandable.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session

from database.models.event import Event
from database.models.track import Track
from database.models.track_history import TrackHistory

logger = logging.getLogger(__name__)


class TimelineEventType(Enum):
    """Intelligent timeline event types"""
    ENTERED = "entered"
    WALKING = "walking"
    STOPPED = "stopped"
    NEAR_LOCATION = "near_location"
    INTERACTION = "interaction"
    EXITED = "exited"
    BRIEF_APPEARANCE = "brief_appearance"
    LONG_STAY = "long_stay"


@dataclass
class IntelligentEvent:
    """Enhanced event with intelligent interpretation"""
    timestamp: datetime
    event_type: TimelineEventType
    description: str
    icon: str
    track_id: str
    location: Optional[str] = None
    duration: Optional[int] = None
    confidence: float = 1.0
    context: Dict[str, Any] = None
    raw_events: List[str] = None  # Original event IDs


class TimelineIntelligence:
    """
    Converts raw events into meaningful, human-readable timeline sequences.
    
    This service:
    1. Analyzes event patterns
    2. Infers behavior context
    3. Groups related events
    4. Generates narrative descriptions
    5. Adds visual indicators
    """
    
    def __init__(self):
        """Initialize timeline intelligence"""
        self.event_icons = {
            TimelineEventType.ENTERED: "🚶",
            TimelineEventType.WALKING: "➡️",
            TimelineEventType.STOPPED: "⏸️",
            TimelineEventType.NEAR_LOCATION: "📍",
            TimelineEventType.INTERACTION: "🤝",
            TimelineEventType.EXITED: "🚪",
            TimelineEventType.BRIEF_APPEARANCE: "⚡",
            TimelineEventType.LONG_STAY: "🏠"
        }
        
        self.location_keywords = {
            'entrance': ['entrance', 'entry', 'door'],
            'checkout': ['checkout', 'counter', 'register', 'cashier'],
            'aisle': ['aisle', 'shelf', 'product'],
            'exit': ['exit', 'leaving', 'departure']
        }
    
    def build_intelligent_timeline(
        self, 
        track_id: str, 
        db: Session,
        context: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Build an intelligent timeline for a specific track
        
        Args:
            track_id: UUID of track to analyze
            db: Database session
            context: Optional context (location info, etc.)
            
        Returns:
            Intelligent timeline with meaningful events
        """
        logger.info(f"🧠 Building intelligent timeline for track: {track_id}")
        
        try:
            # Get raw events for this track
            raw_events = self._get_track_events(track_id, db)
            if not raw_events:
                return []
            
            # Get track movement data
            movement_data = self._get_track_movement_data(track_id, db)
            
            # Analyze and convert to intelligent events
            intelligent_events = self._analyze_event_patterns(raw_events, movement_data, context)
            
            # Post-process and enhance
            enhanced_events = self._enhance_timeline(intelligent_events, movement_data)
            
            # Convert to response format
            timeline = [self._format_intelligent_event(event) for event in enhanced_events]
            
            logger.info(f"✅ Intelligent timeline built: {len(timeline)} meaningful events")
            return timeline
            
        except Exception as e:
            logger.error(f"❌ Timeline intelligence failed: {e}")
            return []
    
    def build_video_intelligent_timeline(
        self, 
        video_id: str, 
        db: Session,
        max_tracks: int = 20
    ) -> Dict[str, Any]:
        """
        Build intelligent timeline for entire video
        
        Args:
            video_id: UUID of video
            db: Database session
            max_tracks: Maximum tracks to include
            
        Returns:
            Video-level intelligent timeline
        """
        logger.info(f"🧠 Building video intelligent timeline: {video_id}")
        
        try:
            # Get all tracks for this video
            tracks = db.query(Track).filter(
                Track.video_id == video_id
            ).order_by(Track.first_seen.asc()).limit(max_tracks).all()
            
            # Build timeline for each track
            track_timelines = {}
            for track in tracks:
                track_timeline = self.build_intelligent_timeline(str(track.id), db)
                if track_timeline:
                    track_timelines[str(track.id)] = track_timeline
            
            # Merge and analyze cross-track patterns
            merged_timeline = self._merge_track_timelines(track_timelines)
            
            # Generate video-level insights
            insights = self._generate_video_insights(track_timelines, tracks)
            
            return {
                'video_id': video_id,
                'timeline_type': 'intelligent_video_timeline',
                'total_tracks': len(tracks),
                'track_timelines': track_timelines,
                'merged_timeline': merged_timeline,
                'insights': insights,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Video timeline intelligence failed: {e}")
            return {'error': str(e)}
    
    def analyze_behavior_patterns(
        self, 
        events: List[IntelligentEvent]
    ) -> Dict[str, Any]:
        """
        Analyze behavior patterns from intelligent events
        
        Args:
            events: List of intelligent events
            
        Returns:
            Behavior analysis
        """
        if not events:
            return {}
        
        # Calculate total duration
        start_time = min(e.timestamp for e in events)
        end_time = max(e.timestamp for e in events)
        total_duration = (end_time - start_time).total_seconds()
        
        # Analyze event types
        event_counts = {}
        for event in events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        # Determine behavior pattern
        behavior_type = self._classify_behavior(events, event_counts, total_duration)
        
        # Calculate movement metrics
        movement_metrics = self._calculate_movement_metrics(events)
        
        return {
            'behavior_type': behavior_type,
            'total_duration_seconds': total_duration,
            'event_counts': event_counts,
            'movement_metrics': movement_metrics,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
    
    def _get_track_events(self, track_id: str, db: Session) -> List[Event]:
        """Get all events for a track"""
        return db.query(Event).filter(
            Event.track_id == track_id
        ).order_by(Event.timestamp.asc()).all()
    
    def _get_track_movement_data(self, track_id: str, db: Session) -> List[Dict]:
        """Get movement data for track analysis"""
        track_history = db.query(TrackHistory).filter(
            TrackHistory.track_id == track_id
        ).order_by(TrackHistory.frame_number.asc()).all()
        
        return [
            {
                'frame_number': th.frame_number,
                'bbox': [th.bbox_x, th.bbox_y, th.bbox_w, th.bbox_h],
                'confidence': th.confidence,
                'timestamp': th.created_at  # Approximated
            }
            for th in track_history
        ]
    
    def _analyze_event_patterns(
        self, 
        raw_events: List[Event], 
        movement_data: List[Dict],
        context: Optional[Dict]
    ) -> List[IntelligentEvent]:
        """Analyze raw events and convert to intelligent events"""
        
        intelligent_events = []
        
        if not raw_events:
            return intelligent_events
        
        # Group consecutive events
        event_groups = self._group_consecutive_events(raw_events)
        
        for group in event_groups:
            intelligent_event = self._convert_event_group(group, movement_data, context)
            if intelligent_event:
                intelligent_events.append(intelligent_event)
        
        # Add inferred events based on movement patterns
        inferred_events = self._infer_events_from_movement(movement_data, raw_events)
        intelligent_events.extend(inferred_events)
        
        # Sort by timestamp
        intelligent_events.sort(key=lambda e: e.timestamp)
        
        return intelligent_events
    
    def _group_consecutive_events(self, events: List[Event]) -> List[List[Event]]:
        """Group consecutive events of similar types"""
        if not events:
            return []
        
        groups = []
        current_group = [events[0]]
        
        for i in range(1, len(events)):
            current_event = events[i]
            previous_event = events[i-1]
            
            # Time gap threshold (5 seconds)
            time_gap = (current_event.timestamp - previous_event.timestamp).total_seconds()
            
            if time_gap <= 5 and current_event.event_type == previous_event.event_type:
                current_group.append(current_event)
            else:
                groups.append(current_group)
                current_group = [current_event]
        
        groups.append(current_group)
        return groups
    
    def _convert_event_group(
        self, 
        event_group: List[Event], 
        movement_data: List[Dict],
        context: Optional[Dict]
    ) -> Optional[IntelligentEvent]:
        """Convert a group of raw events to one intelligent event"""
        
        if not event_group:
            return None
        
        first_event = event_group[0]
        last_event = event_group[-1]
        
        # Determine intelligent event type
        if first_event.event_type == 'track_started':
            event_type = TimelineEventType.ENTERED
            description = "Person entered camera view"
            
        elif first_event.event_type == 'track_ended':
            event_type = TimelineEventType.EXITED
            description = "Person exited camera view"
            
        elif first_event.event_type == 'track_updated':
            # Analyze movement to determine if walking or stopped
            if len(event_group) > 5:
                # Multiple updates suggest movement
                event_type = TimelineEventType.WALKING
                description = "Person walking through area"
            else:
                # Few updates might indicate stopping
                event_type = TimelineEventType.STOPPED
                description = "Person paused in area"
        
        else:
            event_type = TimelineEventType.WALKING
            description = f"Person activity: {first_event.event_type}"
        
        # Calculate duration if multiple events
        duration = None
        if len(event_group) > 1:
            duration = int((last_event.timestamp - first_event.timestamp).total_seconds())
        
        # Infer location from metadata or movement data
        location = self._infer_location(event_group, movement_data, context)
        
        return IntelligentEvent(
            timestamp=first_event.timestamp,
            event_type=event_type,
            description=description,
            icon=self.event_icons.get(event_type, "📋"),
            track_id=str(first_event.track_id) if first_event.track_id else "unknown",
            location=location,
            duration=duration,
            confidence=sum(e.score or 0.8 for e in event_group) / len(event_group),
            context={'event_count': len(event_group)},
            raw_events=[str(e.id) for e in event_group]
        )
    
    def _infer_events_from_movement(
        self, 
        movement_data: List[Dict], 
        raw_events: List[Event]
    ) -> List[IntelligentEvent]:
        """Infer additional events from movement patterns"""
        
        inferred_events = []
        
        if len(movement_data) < 2:
            return inferred_events
        
        # Analyze movement patterns
        for i in range(1, len(movement_data)):
            prev_data = movement_data[i-1]
            curr_data = movement_data[i]
            
            # Calculate movement distance
            prev_center = [
                prev_data['bbox'][0] + prev_data['bbox'][2]/2,
                prev_data['bbox'][1] + prev_data['bbox'][3]/2
            ]
            curr_center = [
                curr_data['bbox'][0] + curr_data['bbox'][2]/2,
                curr_data['bbox'][1] + curr_data['bbox'][3]/2
            ]
            
            distance = ((curr_center[0] - prev_center[0])**2 + (curr_center[1] - prev_center[1])**2)**0.5
            
            # If very little movement for several frames, infer stopping
            if distance < 10:  # Threshold for "not moving"
                # Look ahead to see if this is sustained
                stopped_duration = 1
                for j in range(i+1, min(i+10, len(movement_data))):
                    next_data = movement_data[j]
                    next_center = [
                        next_data['bbox'][0] + next_data['bbox'][2]/2,
                        next_data['bbox'][1] + next_data['bbox'][3]/2
                    ]
                    next_distance = ((next_center[0] - curr_center[0])**2 + (next_center[1] - curr_center[1])**2)**0.5
                    
                    if next_distance < 10:
                        stopped_duration += 1
                    else:
                        break
                
                # If stopped for more than 3 frames, create stopping event
                if stopped_duration >= 3:
                    inferred_events.append(IntelligentEvent(
                        timestamp=curr_data.get('timestamp', datetime.now()),
                        event_type=TimelineEventType.STOPPED,
                        description=f"Person stopped for {stopped_duration} frames",
                        icon=self.event_icons[TimelineEventType.STOPPED],
                        track_id="inferred",
                        duration=stopped_duration,
                        confidence=0.7,
                        context={'movement_analysis': True}
                    ))
        
        return inferred_events
    
    def _infer_location(
        self, 
        events: List[Event], 
        movement_data: List[Dict],
        context: Optional[Dict]
    ) -> Optional[str]:
        """Infer location from event metadata and movement data"""
        
        # Check event metadata for location hints
        for event in events:
            if event.event_metadata:
                metadata = event.event_metadata
                if 'location' in metadata:
                    return metadata['location']
                
                # Look for location keywords in metadata
                metadata_text = str(metadata).lower()
                for location, keywords in self.location_keywords.items():
                    if any(keyword in metadata_text for keyword in keywords):
                        return location
        
        # Analyze movement data for location inference
        if movement_data:
            # Simple heuristic: if near edges, might be entrance/exit
            first_bbox = movement_data[0]['bbox']
            
            # If bbox is near left/right edge, might be entrance/exit
            if first_bbox[0] < 100:  # Near left edge
                return 'entrance'
            elif first_bbox[0] > 1820:  # Near right edge (assuming 1920 width)
                return 'exit'
        
        return None
    
    def _enhance_timeline(
        self, 
        events: List[IntelligentEvent], 
        movement_data: List[Dict]
    ) -> List[IntelligentEvent]:
        """Post-process timeline to add enhancements"""
        
        enhanced_events = []
        
        for event in events:
            # Enhance description based on duration
            if event.duration:
                if event.duration > 30:
                    event.description += f" (stayed {event.duration}s)"
                elif event.duration < 3:
                    event.description += " (brief)"
            
            # Enhance description based on location
            if event.location:
                event.description += f" near {event.location}"
            
            enhanced_events.append(event)
        
        return enhanced_events
    
    def _merge_track_timelines(self, track_timelines: Dict[str, List]) -> List[Dict]:
        """Merge multiple track timelines into chronological order"""
        
        all_events = []
        
        for track_id, timeline in track_timelines.items():
            for event in timeline:
                event['track_id'] = track_id
                all_events.append(event)
        
        # Sort by timestamp
        all_events.sort(key=lambda e: e.get('timestamp', ''))
        
        return all_events
    
    def _generate_video_insights(
        self, 
        track_timelines: Dict[str, List], 
        tracks: List[Track]
    ) -> Dict[str, Any]:
        """Generate insights from video timeline analysis"""
        
        total_tracks = len(track_timelines)
        total_events = sum(len(timeline) for timeline in track_timelines.values())
        
        # Analyze activity patterns
        activity_periods = self._analyze_activity_periods(track_timelines)
        
        # Common behavior patterns
        behavior_patterns = self._identify_common_patterns(track_timelines)
        
        return {
            'total_tracks_analyzed': total_tracks,
            'total_intelligent_events': total_events,
            'activity_periods': activity_periods,
            'behavior_patterns': behavior_patterns,
            'average_events_per_track': total_events / max(total_tracks, 1)
        }
    
    def _format_intelligent_event(self, event: IntelligentEvent) -> Dict[str, Any]:
        """Format intelligent event for API response"""
        return {
            'timestamp': event.timestamp.strftime('%H:%M:%S'),
            'event_type': event.event_type.value,
            'description': event.description,
            'icon': event.icon,
            'track_id': event.track_id,
            'location': event.location,
            'duration': event.duration,
            'confidence': round(event.confidence, 2),
            'context': event.context or {},
            'raw_events': event.raw_events or []
        }
    
    def _classify_behavior(
        self, 
        events: List[IntelligentEvent], 
        event_counts: Dict[str, int],
        total_duration: float
    ) -> str:
        """Classify overall behavior pattern"""
        
        if total_duration < 10:
            return 'brief_passage'
        elif total_duration > 120:
            return 'extended_stay'
        elif event_counts.get('stopped', 0) > 2:
            return 'browsing_behavior'
        elif event_counts.get('walking', 0) > 5:
            return 'transit_behavior'
        else:
            return 'normal_activity'
    
    def _calculate_movement_metrics(self, events: List[IntelligentEvent]) -> Dict[str, float]:
        """Calculate movement-related metrics"""
        
        walking_events = [e for e in events if e.event_type == TimelineEventType.WALKING]
        stopped_events = [e for e in events if e.event_type == TimelineEventType.STOPPED]
        
        return {
            'mobility_ratio': len(walking_events) / max(len(events), 1),
            'stop_frequency': len(stopped_events) / max(len(events), 1),
            'average_stop_duration': sum(e.duration or 0 for e in stopped_events) / max(len(stopped_events), 1)
        }
    
    # Placeholder methods
    def _analyze_activity_periods(self, track_timelines: Dict) -> Dict:
        """Analyze peak activity periods"""
        return {'peak_hours': [], 'quiet_periods': []}
    
    def _identify_common_patterns(self, track_timelines: Dict) -> List[str]:
        """Identify common behavior patterns"""
        return ['entrance_to_exit', 'browsing_pattern', 'quick_transit']