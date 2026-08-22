"""
Timeline Builder - Professional Timeline View

Phase 12 / Phase 17 Implementation:

Instead of:
    Track 17, Frame 400, Frame 500...

Build:
    10:31 - Entered Camera
    10:33 - Walking
    10:36 - Stopped
    10:38 - Exited

Creates human-readable timeline from raw events.
Also provides DB-backed overloads (build_video_timeline, build_track_timeline)
that accept a video_id / track_id + SQLAlchemy Session rather than pre-fetched
event lists — required by investigation_service_advanced.
"""

from __future__ import annotations

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session


class TimelineBuilder:
    """Builds professional timeline views from raw events"""
    
    def __init__(self, video_fps: int = 30):
        """
        Initialize timeline builder
        
        Args:
            video_fps: Video FPS for timestamp calculation
        """
        self.video_fps = video_fps
    
    def build_timeline(
        self, 
        events: List[Dict[str, Any]],
        video_start_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Build professional timeline from raw events
        
        Args:
            events: List of events from database
            video_start_time: Optional video start time for absolute timestamps
            
        Returns:
            List of timeline entries with human-readable format
        """
        if not events:
            return []
        
        timeline = []
        video_start = video_start_time or events[0].get('timestamp', datetime.now())
        
        for event in events:
            entry = self._build_timeline_entry(event, video_start)
            if entry:
                timeline.append(entry)
        
        return timeline
    
    # build_track_timeline is defined below alongside the DB-backed overloads.
    
    def build_video_summary(
        self,
        events: List[Dict[str, Any]],
        tracks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build summary timeline for entire video
        
        Args:
            events: All video events
            tracks: All video tracks
            
        Returns:
            Video timeline summary
        """
        # Group events by type
        events_by_type = {}
        for event in events:
            event_type = event.get('event_type', 'unknown')
            if event_type not in events_by_type:
                events_by_type[event_type] = []
            events_by_type[event_type].append(event)
        
        # Build track summaries
        track_summaries = []
        for track in tracks[:10]:  # Limit to 10 for summary
            track_summaries.append({
                'track_id': str(track.get('id')),
                'class_label': track.get('class_label', 'person'),
                'event_count': track.get('event_count', 0)
            })
        
        return {
            'total_events': len(events),
            'total_tracks': len(tracks),
            'events_by_type': {k: len(v) for k, v in events_by_type.items()},
            'tracks': track_summaries,
            'timeline_highlights': self._extract_highlights(events)
        }
    
    def _build_timeline_entry(
        self, 
        event: Dict[str, Any],
        video_start: datetime
    ) -> Optional[Dict[str, Any]]:
        """Build a single timeline entry"""
        event_type = event.get('event_type')
        timestamp = event.get('timestamp')
        
        if not timestamp:
            return None
        
        # Calculate relative time from video start
        relative_seconds = (timestamp - video_start).total_seconds()
        time_formatted = self._format_time(relative_seconds)
        
        # Build entry based on event type
        entry = {
            'time': time_formatted,
            'timestamp': timestamp.isoformat(),
            'event_type': event_type,
            'track_id': str(event.get('track_id')) if event.get('track_id') else None,
            'confidence': event.get('score', 0.0),
            'description': self._get_event_description(event),
            'icon': self._get_event_icon(event_type),
            'metadata': event.get('event_metadata') or event.get('metadata', {})
        }
        
        return entry
    
    def _build_track_event_entry(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build timeline entry for track-specific event"""
        event_type = event.get('event_type')
        timestamp = event.get('timestamp')
        metadata = event.get('event_metadata') or event.get('metadata', {})
        
        time_str = "Unknown"
        if timestamp:
            if isinstance(timestamp, datetime):
                time_str = timestamp.strftime("%H:%M:%S")
            else:
                time_str = str(timestamp)
        
        # Create descriptive entry
        description = self._get_track_event_description(event_type, metadata)
        
        return {
            'time': time_str,
            'event': event_type,
            'description': description,
            'icon': self._get_event_icon(event_type),
            'details': metadata
        }
    
    def _get_event_description(self, event: Dict[str, Any]) -> str:
        """Get human-readable event description"""
        event_type = event.get('event_type')
        metadata = event.get('event_metadata') or event.get('metadata', {})
        
        descriptions = {
            'object_detected': 'Person detected in frame',
            'track_started': 'Person entered camera view',
            'track_updated': 'Person movement tracked',
            'track_ended': 'Person exited camera view'
        }
        
        base_description = descriptions.get(event_type, f'Event: {event_type}')
        
        # Add additional context
        if event_type == 'track_ended':
            duration = metadata.get('duration_frames', 0)
            if duration > 0:
                duration_seconds = duration / self.video_fps
                base_description += f' (visible for {self._format_duration(duration_seconds)})'
        
        return base_description
    
    def _get_track_event_description(self, event_type: str, metadata: Dict[str, Any]) -> str:
        """Get description for track event"""
        descriptions = {
            'object_detected': 'Detected in frame',
            'track_started': 'Entered camera view',
            'track_updated': 'Movement tracked',
            'track_ended': f"Exited camera view (visible for {metadata.get('duration_frames', 0)} frames)"
        }
        
        return descriptions.get(event_type, event_type.replace('_', ' ').title())
    
    def _get_event_icon(self, event_type: str) -> str:
        """Get icon for event type"""
        icons = {
            'object_detected': '👁️',
            'track_started': '🚶',
            'track_updated': '➡️',
            'track_ended': '🚪'
        }
        return icons.get(event_type, '📋')
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds to HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def _build_track_summary(self, timeline: List[Dict], metadata: Optional[Dict]) -> str:
        """Build summary text for track"""
        if not timeline:
            return "No activity recorded"
        
        first_event = timeline[0]['event'] if timeline else 'unknown'
        last_event = timeline[-1]['event'] if len(timeline) > 1 else first_event
        
        event_count = len(timeline)
        
        summary_parts = []
        
        if first_event == 'track_started':
            summary_parts.append("Entered camera")
        
        summary_parts.append(f"{event_count} events recorded")
        
        if last_event == 'track_ended':
            summary_parts.append("exited")
        
        return " - ".join(summary_parts)
    
    def _extract_highlights(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract key highlights from events"""
        highlights = []
        
        # Track entries and exits
        for event in events:
            event_type = event.get('event_type')
            if event_type in ['track_started', 'track_ended']:
                timestamp = event.get('timestamp')
                if timestamp:
                    if isinstance(timestamp, datetime):
                        time_str = timestamp.strftime("%H:%M:%S")
                    else:
                        time_str = str(timestamp)
                    
                    highlights.append({
                        'time': time_str,
                        'type': 'entry' if event_type == 'track_started' else 'exit',
                        'description': 'Person entered' if event_type == 'track_started' else 'Person exited',
                        'track_id': str(event.get('track_id')) if event.get('track_id') else None
                    })
        
        return highlights[:20]  # Limit to 20 highlights


    # ------------------------------------------------------------------
    # Missing method — called by SearchOrchestrator and
    # investigation_service_advanced as build_events_timeline(events)
    # ------------------------------------------------------------------

    def build_events_timeline(
        self,
        events: List[Dict[str, Any]],
        video_start_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Alias for build_timeline — keeps callers that use the older name working."""
        return self.build_timeline(events, video_start_time)

    # ------------------------------------------------------------------
    # DB-backed overloads  (Phase 17)
    # Called by investigation_service_advanced with (video_id, db)
    # and (track_id, db) signatures.
    # ------------------------------------------------------------------

    def build_video_timeline(
        self,
        video_id: str | uuid.UUID,
        db: Session,
    ) -> List[Dict[str, Any]]:
        """
        Build a full timeline for a video by querying the events table.

        Args:
            video_id: UUID of the video
            db: SQLAlchemy session

        Returns:
            List of timeline entries ordered by timestamp
        """
        from database.models.event import Event

        vid = uuid.UUID(str(video_id)) if not isinstance(video_id, uuid.UUID) else video_id
        rows = (
            db.query(Event)
            .filter(Event.video_id == vid)
            .order_by(Event.timestamp.asc())
            .all()
        )

        if not rows:
            return []

        video_start = rows[0].timestamp
        events_as_dicts = [
            {
                "event_type": r.event_type,
                "track_id": r.track_id,
                "timestamp": r.timestamp,
                "score": r.score,
                "frame_number": r.frame_number,
                "metadata": r.event_metadata or {},
            }
            for r in rows
        ]
        return self.build_timeline(events_as_dicts, video_start)

    def build_track_timeline(
        self,
        track_id_or_str: str | uuid.UUID,
        db_or_events,
        track_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Overloaded: accepts either
          - (track_id, db)  → queries the DB and returns track timeline dict
          - (track_id, events_list)  → original in-memory behaviour

        Args:
            track_id_or_str: Track UUID
            db_or_events: SQLAlchemy Session OR list of event dicts
            track_metadata: Optional extra metadata

        Returns:
            Track timeline dict with summary, first_seen, last_seen, timeline list
        """
        track_id_str = str(track_id_or_str)

        if isinstance(db_or_events, Session):
            # DB-backed path
            from database.models.event import Event
            import uuid as _uuid
            tid = _uuid.UUID(track_id_str)
            rows = (
                db_or_events.query(Event)
                .filter(Event.track_id == tid)
                .order_by(Event.timestamp.asc())
                .all()
            )
            events: List[Dict[str, Any]] = [
                {
                    "event_type": r.event_type,
                    "track_id": r.track_id,
                    "timestamp": r.timestamp,
                    "score": r.score,
                    "frame_number": r.frame_number,
                    "metadata": r.event_metadata or {},
                }
                for r in rows
            ]
        else:
            events = db_or_events  # already a list

        # Delegate to original list-based implementation
        return self._build_track_timeline_from_list(track_id_str, events, track_metadata)

    def _build_track_timeline_from_list(
        self,
        track_id: str,
        events: List[Dict[str, Any]],
        track_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal: build track timeline from an event list."""
        if not events:
            return {
                "track_id": track_id,
                "summary": "No events recorded",
                "timeline": [],
            }

        sorted_events = sorted(events, key=lambda e: e.get("timestamp", datetime.now()))
        timeline = []
        first_seen = None
        last_seen = None

        for event in sorted_events:
            timestamp = event.get("timestamp")
            if timestamp:
                if first_seen is None:
                    first_seen = timestamp
                last_seen = timestamp
            entry = self._build_track_event_entry(event)
            if entry:
                timeline.append(entry)

        duration = None
        if first_seen and last_seen:
            duration_seconds = (last_seen - first_seen).total_seconds()
            duration = self._format_duration(duration_seconds)

        summary = self._build_track_summary(timeline, track_metadata)

        return {
            "track_id": track_id,
            "first_seen": first_seen.isoformat() if first_seen else None,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "duration": duration,
            "total_events": len(timeline),
            "summary": summary,
            "timeline": timeline,
        }


def build_timeline_from_events(
    events: List[Dict[str, Any]],
    video_fps: int = 30
) -> List[Dict[str, Any]]:
    """
    Convenience function to build timeline from events

    Args:
        events: List of events
        video_fps: Video FPS

    Returns:
        Professional timeline view
    """
    builder = TimelineBuilder(video_fps=video_fps)
    return builder.build_timeline(events)
