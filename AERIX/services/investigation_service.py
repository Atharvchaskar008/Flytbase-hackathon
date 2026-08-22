"""
Investigation Service - Unified Search Interface

Phase 11 Implementation:

Instead of calling five APIs separately, one service returns everything:

Input: "Find person wearing red cap"

Output:
    Timeline
    ↓
    Events
    ↓
    Tracks
    ↓
    Matching Clips

One service call for complete investigation results.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from database.models.video import Video
from database.models.track import Track
from database.models.event import Event
from database.models.camera import Camera
from services.timeline_builder import TimelineBuilder


class InvestigationService:
    """
    Unified service for video investigations
    
    Combines timeline, events, tracks, and clips in one response
    """
    
    def __init__(self, db: Session):
        """
        Initialize investigation service
        
        Args:
            db: Database session
        """
        self.db = db
        self.timeline_builder = TimelineBuilder()
    
    def search(
        self,
        query: str,
        video_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search for events, tracks, and generate timeline
        
        Args:
            query: Search query (e.g., "red cap", "person walking")
            video_id: Optional video filter
            camera_id: Optional camera filter
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum results
            
        Returns:
            Complete investigation results
        """
        # Build base query
        events_query = self.db.query(Event)
        tracks_query = self.db.query(Track)
        
        # Apply filters
        if video_id:
            events_query = events_query.filter(Event.video_id == video_id)
            tracks_query = tracks_query.filter(Track.video_id == video_id)
        
        if camera_id:
            events_query = events_query.filter(Event.camera_id == camera_id)
            tracks_query = tracks_query.filter(Track.camera_id == camera_id)
        
        if start_time:
            events_query = events_query.filter(Event.timestamp >= start_time)
        
        if end_time:
            events_query = events_query.filter(Event.timestamp <= end_time)
        
        # Execute queries
        events = events_query.order_by(Event.timestamp.asc()).limit(limit * 10).all()
        tracks = tracks_query.limit(limit).all()
        
        # Build timeline
        timeline = self.timeline_builder.build_timeline([
            {
                'event_type': e.event_type,
                'timestamp': e.timestamp,
                'track_id': str(e.track_id) if e.track_id else None,
                'score': e.score,
                'metadata': e.event_metadata
            }
            for e in events
        ])
        
        # Build track summaries
        track_summaries = []
        for track in tracks:
            track_events = [e for e in events if e.track_id == track.id]
            track_timeline = self.timeline_builder.build_track_timeline(
                str(track.id),
                [
                    {
                        'event_type': e.event_type,
                        'timestamp': e.timestamp,
                        'score': e.score,
                        'metadata': e.event_metadata
                    }
                    for e in track_events
                ]
            )
            track_summaries.append(track_timeline)
        
        # Build result
        return {
            'query': query,
            'filters': {
                'video_id': video_id,
                'camera_id': camera_id,
                'start_time': start_time.isoformat() if start_time else None,
                'end_time': end_time.isoformat() if end_time else None
            },
            'summary': {
                'total_events': len(events),
                'total_tracks': len(tracks),
                'timeline_entries': len(timeline)
            },
            'timeline': timeline,
            'events': self._format_events(events[:limit]),
            'tracks': track_summaries[:limit],
            'clips': self._generate_clip_links(events[:limit])
        }
    
    def investigate_track(
        self,
        track_id: str,
        include_clip_urls: bool = True
    ) -> Dict[str, Any]:
        """
        Get complete information about a specific track
        
        Args:
            track_id: Track UUID
            include_clip_urls: Whether to include clip URLs
            
        Returns:
            Complete track investigation results
        """
        # Get track
        track = self.db.query(Track).filter(Track.id == track_id).first()
        if not track:
            return {
                'error': 'Track not found',
                'track_id': track_id
            }
        
        # Get events for this track
        events = self.db.query(Event).filter(
            Event.track_id == track_id
        ).order_by(Event.timestamp.asc()).all()
        
        # Build timeline
        timeline = self.timeline_builder.build_track_timeline(
            track_id,
            [
                {
                    'event_type': e.event_type,
                    'timestamp': e.timestamp,
                    'score': e.score,
                    'metadata': e.event_metadata
                }
                for e in events
            ]
        )
        
        # Get video and camera info
        video = self.db.query(Video).filter(Video.id == track.video_id).first()
        camera = self.db.query(Camera).filter(Camera.id == track.camera_id).first()
        
        result = {
            'track': {
                'id': str(track.id),
                'class_label': track.class_label,
                'first_seen': track.first_seen.isoformat() if track.first_seen else None,
                'last_seen': track.last_seen.isoformat() if track.last_seen else None,
                'reid_global_id': track.reid_global_id
            },
            'video': {
                'id': str(video.id) if video else None,
                'filename': video.filename if video else None,
                'status': video.status if video else None
            },
            'camera': {
                'id': str(camera.id) if camera else None,
                'name': camera.name if camera else None,
                'location': camera.location if camera else None
            },
            'timeline': timeline,
            'events': self._format_events(events),
            'total_events': len(events)
        }
        
        # Add clip URLs
        if include_clip_urls and events:
            result['clips'] = self._generate_clip_links(events)
        
        return result
    
    def investigate_video(
        self,
        video_id: str
    ) -> Dict[str, Any]:
        """
        Get complete investigation results for a video
        
        Args:
            video_id: Video UUID
            
        Returns:
            Complete video investigation results
        """
        # Get video
        video = self.db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return {
                'error': 'Video not found',
                'video_id': video_id
            }
        
        # Get events and tracks
        events = self.db.query(Event).filter(
            Event.video_id == video_id
        ).order_by(Event.timestamp.asc()).all()
        
        tracks = self.db.query(Track).filter(
            Track.video_id == video_id
        ).all()
        
        # Build timeline
        timeline = self.timeline_builder.build_timeline([
            {
                'event_type': e.event_type,
                'timestamp': e.timestamp,
                'track_id': str(e.track_id) if e.track_id else None,
                'score': e.score,
                'metadata': e.event_metadata
            }
            for e in events
        ])
        
        # Build summary
        summary = self.timeline_builder.build_video_summary(
            [
                {
                    'event_type': e.event_type,
                    'timestamp': e.timestamp,
                    'track_id': str(e.track_id) if e.track_id else None,
                    'score': e.score,
                    'event_metadata': e.event_metadata
                }
                for e in events
            ],
            [
                {
                    'id': str(t.id),
                    'class_label': t.class_label,
                    'event_count': len([e for e in events if e.track_id == t.id])
                }
                for t in tracks
            ]
        )
        
        return {
            'video': {
                'id': str(video.id),
                'filename': video.filename,
                'status': video.status,
                'progress': video.progress,
                'progress_message': video.progress_message,
                'frames_total': video.frames_total,
                'frames_processed': video.frames_processed,
                'created_at': video.created_at.isoformat(),
                'duration_seconds': video.duration_seconds
            },
            'summary': summary,
            'timeline': timeline,
            'tracks': [
                {
                    'id': str(t.id),
                    'class_label': t.class_label,
                    'first_seen': t.first_seen.isoformat() if t.first_seen else None,
                    'last_seen': t.last_seen.isoformat() if t.last_seen else None,
                    'reid_global_id': t.reid_global_id
                }
                for t in tracks
            ],
            'total_events': len(events),
            'total_tracks': len(tracks)
        }
    
    def find_person_by_time(
        self,
        timestamp: datetime,
        camera_id: Optional[str] = None,
        time_window_seconds: int = 30
    ) -> Dict[str, Any]:
        """
        Find persons visible at a specific time
        
        Args:
            timestamp: Target timestamp
            camera_id: Optional camera filter
            time_window_seconds: Time window around timestamp
            
        Returns:
            Persons visible at that time
        """
        start = timestamp - timedelta(seconds=time_window_seconds)
        end = timestamp + timedelta(seconds=time_window_seconds)
        
        # Query tracks active during this time
        query = self.db.query(Track).filter(
            Track.first_seen <= end,
            Track.last_seen >= start
        )
        
        if camera_id:
            query = query.filter(Track.camera_id == camera_id)
        
        tracks = query.all()
        
        return {
            'timestamp': timestamp.isoformat(),
            'time_window': f"±{time_window_seconds}s",
            'total_persons': len(tracks),
            'persons': [
                {
                    'track_id': str(t.id),
                    'class_label': t.class_label,
                    'first_seen': t.first_seen.isoformat() if t.first_seen else None,
                    'last_seen': t.last_seen.isoformat() if t.last_seen else None,
                    'duration_seconds': (t.last_seen - t.first_seen).total_seconds() if t.last_seen and t.first_seen else 0
                }
                for t in tracks
            ]
        }
    
    def _format_events(self, events: List[Event]) -> List[Dict[str, Any]]:
        """Format events for response"""
        return [
            {
                'id': str(e.id),
                'event_type': e.event_type,
                'timestamp': e.timestamp.isoformat() if e.timestamp else None,
                'track_id': str(e.track_id) if e.track_id else None,
                'video_id': str(e.video_id) if e.video_id else None,
                'camera_id': str(e.camera_id) if e.camera_id else None,
                'score': e.score,
                'metadata': e.event_metadata
            }
            for e in events
        ]
    
    def _generate_clip_links(self, events: List[Event]) -> List[Dict[str, Any]]:
        """Generate clip links for events"""
        clips = []
        for event in events[:10]:  # Limit to 10 clips
            if event.id:
                clips.append({
                    'event_id': str(event.id),
                    'event_type': event.event_type,
                    'clip_url': f"/clip/{event.id}",
                    'download_url': f"/clip/{event.id}/download",
                    'timestamp': event.timestamp.isoformat() if event.timestamp else None
                })
        return clips


# Convenience function
def investigate(
    db: Session,
    query: str = None,
    video_id: str = None,
    track_id: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function for investigations
    
    Usage:
        # Investigate a video
        result = investigate(db, video_id="uuid")
        
        # Investigate a track
        result = investigate(db, track_id="uuid")
        
        # Search
        result = investigate(db, query="red cap", video_id="uuid")
    """
    service = InvestigationService(db)
    
    if track_id:
        return service.investigate_track(track_id)
    elif video_id and not query:
        return service.investigate_video(video_id)
    elif query:
        return service.search(query, video_id=video_id, **kwargs)
    else:
        return {
            'error': 'Please provide query, video_id, or track_id'
        }
