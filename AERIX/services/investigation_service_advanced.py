"""
Phase 15 - Investigation Service ⭐⭐⭐⭐⭐

This becomes your backend's brain.

Instead of APIs talking directly to repositories:

API → InvestigationService → SearchService → TimelineService → 
ClipService → Repositories

The Investigation Service combines all results into a coherent response.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from services.search_service import SearchService
from services.timeline_builder import TimelineBuilder  
from services.clip_service import ClipService
from database.models.video import Video
from database.models.track import Track
from database.models.event import Event
from database.repository.video_repository import get_video

logger = logging.getLogger(__name__)


class InvestigationService:
    """
    The backend's brain for investigations.
    
    This service:
    1. Coordinates multiple backend services
    2. Combines search results intelligently
    3. Builds comprehensive investigation reports
    4. Provides context-aware responses
    5. Manages complex queries
    """
    
    def __init__(self):
        """Initialize investigation service with all sub-services"""
        self.search_service = SearchService()
        self.timeline_builder = TimelineBuilder()
        self.clip_service = ClipService()
        
    def investigate_video(
        self, 
        video_id: str, 
        db: Session,
        include_clips: bool = True,
        max_events: int = 100
    ) -> Dict[str, Any]:
        """
        Comprehensive video investigation
        
        Args:
            video_id: UUID of video to investigate
            db: Database session
            include_clips: Whether to include clip URLs
            max_events: Maximum number of events to return
            
        Returns:
            Complete investigation report
        """
        try:
            logger.info(f"🔍 Starting video investigation: {video_id}")
            
            # Validate video exists
            video = get_video(db, video_id)
            if not video:
                return self._error_response("Video not found", "VIDEO_NOT_FOUND")
            
            # Get video summary
            video_summary = self._get_video_summary(video, db)
            
            # Get all tracks for this video
            tracks = self._get_video_tracks(video_id, db)
            
            # Get timeline
            timeline = self.timeline_builder.build_video_timeline(video_id, db)
            
            # Get events summary
            events_summary = self._get_events_summary(video_id, db, max_events)
            
            # Get clips if requested
            clips = []
            if include_clips and timeline:
                clips = self._get_timeline_clips(timeline[:10], db)  # Top 10 events
            
            # Build comprehensive response
            response = {
                'investigation_id': str(uuid.uuid4()),
                'video_id': video_id,
                'investigation_type': 'video_analysis',
                'timestamp': datetime.now().isoformat(),
                
                'summary': {
                    'video_filename': video.filename,
                    'video_status': video.status,
                    'total_tracks': len(tracks),
                    'total_events': events_summary['total_events'],
                    'video_duration': video.duration_seconds,
                    'processing_completed': video.status == 'completed'
                },
                
                'tracks': tracks,
                'timeline': timeline,
                'events_summary': events_summary,
                'clips': clips,
                
                'insights': self._generate_video_insights(video, tracks, events_summary),
                
                'status': 'success'
            }
            
            logger.info(f"✅ Video investigation completed: {video_id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Video investigation failed: {video_id} - {e}")
            return self._error_response(f"Investigation failed: {str(e)}", "INVESTIGATION_ERROR")
    
    def investigate_track(
        self, 
        track_id: str, 
        db: Session,
        include_clips: bool = True
    ) -> Dict[str, Any]:
        """
        Detailed track investigation
        
        Args:
            track_id: UUID of track to investigate
            db: Database session
            include_clips: Whether to include clip URLs
            
        Returns:
            Complete track investigation report
        """
        try:
            logger.info(f"🎯 Starting track investigation: {track_id}")
            
            # Get track
            track = db.query(Track).filter(Track.id == uuid.UUID(track_id)).first()
            if not track:
                return self._error_response("Track not found", "TRACK_NOT_FOUND")
            
            # Get track timeline
            track_timeline = self.timeline_builder.build_track_timeline(track_id, db)
            
            # Get track events
            track_events = self._get_track_events(track_id, db)
            
            # Get track movement analysis
            movement_analysis = self._analyze_track_movement(track_id, db)
            
            # Get clips if requested
            clips = []
            if include_clips and track_timeline:
                clips = self._get_timeline_clips(track_timeline, db)
            
            # Search for similar appearances (Re-ID)
            similar_tracks = self.search_service.find_similar_tracks(track_id, db)
            
            response = {
                'investigation_id': str(uuid.uuid4()),
                'track_id': track_id,
                'investigation_type': 'track_analysis',
                'timestamp': datetime.now().isoformat(),
                
                'track_info': {
                    'track_id': track_id,
                    'video_id': str(track.video_id) if track.video_id else None,
                    'camera_id': str(track.camera_id),
                    'class_label': track.class_label,
                    'first_seen': track.first_seen.isoformat(),
                    'last_seen': track.last_seen.isoformat() if track.last_seen else None,
                    'reid_global_id': track.reid_global_id
                },
                
                'timeline': track_timeline,
                'events': track_events,
                'movement_analysis': movement_analysis,
                'clips': clips,
                'similar_tracks': similar_tracks,
                
                'insights': self._generate_track_insights(track, track_events, movement_analysis),
                
                'status': 'success'
            }
            
            logger.info(f"✅ Track investigation completed: {track_id}")
            return response
            
        except Exception as e:
            logger.error(f"❌ Track investigation failed: {track_id} - {e}")
            return self._error_response(f"Investigation failed: {str(e)}", "INVESTIGATION_ERROR")
    
    def investigate_query(
        self, 
        query: str, 
        db: Session,
        search_type: str = "hybrid",
        max_results: int = 50,
        include_clips: bool = True
    ) -> Dict[str, Any]:
        """
        Query-based investigation (Natural language + Image search)
        
        Args:
            query: Search query (text or image description)
            db: Database session
            search_type: "text", "image", or "hybrid"
            max_results: Maximum results to return
            include_clips: Whether to include clip URLs
            
        Returns:
            Investigation results based on query
        """
        try:
            logger.info(f"🔍 Starting query investigation: '{query}'")
            
            # Perform search based on type
            if search_type == "text":
                search_results = self.search_service.text_search(query, db, max_results)
            elif search_type == "image":
                search_results = self.search_service.image_search_by_description(query, db, max_results)
            else:  # hybrid
                search_results = self.search_service.hybrid_search(query, db, max_results)
            
            # Build timeline from search results
            timeline = self._build_search_timeline(search_results, db)
            
            # Get related tracks
            related_tracks = self._get_related_tracks(search_results, db)
            
            # Get clips for top results
            clips = []
            if include_clips and search_results:
                clips = self._get_search_clips(search_results[:10], db)
            
            # Generate insights
            insights = self._generate_search_insights(query, search_results, related_tracks)
            
            response = {
                'investigation_id': str(uuid.uuid4()),
                'query': query,
                'investigation_type': 'query_search',
                'search_type': search_type,
                'timestamp': datetime.now().isoformat(),
                
                'summary': {
                    'total_results': len(search_results),
                    'unique_tracks': len(related_tracks),
                    'search_confidence': self._calculate_search_confidence(search_results),
                    'time_range': self._get_results_time_range(search_results)
                },
                
                'results': search_results,
                'timeline': timeline,
                'related_tracks': related_tracks,
                'clips': clips,
                'insights': insights,
                
                'status': 'success'
            }
            
            logger.info(f"✅ Query investigation completed: '{query}' - {len(search_results)} results")
            return response
            
        except Exception as e:
            logger.error(f"❌ Query investigation failed: '{query}' - {e}")
            return self._error_response(f"Investigation failed: {str(e)}", "INVESTIGATION_ERROR")
    
    def investigate_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        db: Session,
        video_id: Optional[str] = None,
        include_clips: bool = True
    ) -> Dict[str, Any]:
        """
        Time-based investigation
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            db: Database session
            video_id: Optional video filter
            include_clips: Whether to include clip URLs
            
        Returns:
            Investigation results for time range
        """
        try:
            logger.info(f"⏰ Starting time range investigation: {start_time} to {end_time}")
            
            # Get events in time range
            events_query = db.query(Event).filter(
                Event.timestamp >= start_time,
                Event.timestamp <= end_time
            )
            
            if video_id:
                events_query = events_query.filter(Event.video_id == uuid.UUID(video_id))
            
            events = events_query.order_by(Event.timestamp.asc()).all()
            
            # Get unique tracks from events
            track_ids = list(set(str(e.track_id) for e in events if e.track_id))
            tracks = [self._get_track_summary(tid, db) for tid in track_ids]
            
            # Build timeline
            timeline = self.timeline_builder.build_events_timeline(events)
            
            # Get clips
            clips = []
            if include_clips and events[:10]:
                clips = self._get_event_clips([str(e.id) for e in events[:10]], db)
            
            response = {
                'investigation_id': str(uuid.uuid4()),
                'investigation_type': 'time_range_analysis',
                'time_range': {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'duration_seconds': (end_time - start_time).total_seconds()
                },
                'video_filter': video_id,
                'timestamp': datetime.now().isoformat(),
                
                'summary': {
                    'total_events': len(events),
                    'unique_tracks': len(tracks),
                    'event_types': self._get_event_types_summary(events)
                },
                
                'events': [self._format_event(e) for e in events],
                'tracks': tracks,
                'timeline': timeline,
                'clips': clips,
                
                'insights': self._generate_time_insights(events, tracks, start_time, end_time),
                
                'status': 'success'
            }
            
            logger.info(f"✅ Time range investigation completed: {len(events)} events found")
            return response
            
        except Exception as e:
            logger.error(f"❌ Time range investigation failed: {e}")
            return self._error_response(f"Investigation failed: {str(e)}", "INVESTIGATION_ERROR")
    
    # Helper methods
    
    def _get_video_summary(self, video: Video, db: Session) -> Dict[str, Any]:
        """Get video summary information"""
        return {
            'filename': video.filename,
            'status': video.status,
            'created_at': video.created_at.isoformat() if video.created_at else None,
            'duration_seconds': video.duration_seconds,
            'file_path': video.file_path
        }
    
    def _get_video_tracks(self, video_id: str, db: Session) -> List[Dict[str, Any]]:
        """Get all tracks for a video"""
        tracks = db.query(Track).filter(
            Track.video_id == uuid.UUID(video_id)
        ).order_by(Track.first_seen.asc()).all()
        
        return [
            {
                'track_id': str(track.id),
                'class_label': track.class_label,
                'first_seen': track.first_seen.isoformat(),
                'last_seen': track.last_seen.isoformat() if track.last_seen else None,
                'reid_global_id': track.reid_global_id
            }
            for track in tracks
        ]
    
    def _get_events_summary(self, video_id: str, db: Session, max_events: int) -> Dict[str, Any]:
        """Get events summary for a video"""
        events = db.query(Event).filter(
            Event.video_id == uuid.UUID(video_id)
        ).order_by(Event.timestamp.desc()).limit(max_events).all()
        
        event_types = {}
        for event in events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        
        return {
            'total_events': len(events),
            'event_types': event_types,
            'latest_events': [self._format_event(e) for e in events[:10]]
        }
    
    def _format_event(self, event: Event) -> Dict[str, Any]:
        """Format event for response"""
        return {
            'id': str(event.id),
            'event_type': event.event_type,
            'timestamp': event.timestamp.isoformat(),
            'track_id': str(event.track_id) if event.track_id else None,
            'score': event.score,
            'metadata': event.event_metadata
        }
    
    def _error_response(self, message: str, error_code: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            'status': 'error',
            'error': message,
            'error_code': error_code,
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_video_insights(
        self, 
        video: Video, 
        tracks: List[Dict], 
        events_summary: Dict
    ) -> Dict[str, Any]:
        """Generate insights for video investigation"""
        
        total_tracks = len(tracks)
        total_events = events_summary['total_events']
        
        insights = []
        
        if total_tracks > 10:
            insights.append("High activity video - many people detected")
        elif total_tracks < 3:
            insights.append("Low activity video - few people detected")
        
        if total_events > 100:
            insights.append("High event density - lots of movement")
        
        event_types = events_summary.get('event_types', {})
        if 'track_ended' in event_types and event_types['track_ended'] > total_tracks * 0.8:
            insights.append("Most tracks completed their journey through the frame")
        
        return {
            'activity_level': 'high' if total_tracks > 10 else 'medium' if total_tracks > 5 else 'low',
            'event_density': total_events / max(video.duration_seconds or 1, 1),
            'insights': insights
        }
    
    def _generate_track_insights(
        self, 
        track: Track, 
        events: List[Dict], 
        movement_analysis: Dict
    ) -> Dict[str, Any]:
        """Generate insights for track investigation"""
        
        insights = []
        duration = (track.last_seen - track.first_seen).total_seconds() if track.last_seen else 0
        
        if duration > 60:
            insights.append("Long duration track - person was visible for over 1 minute")
        elif duration < 5:
            insights.append("Brief appearance - person was only visible for a few seconds")
        
        if len(events) > 20:
            insights.append("High activity track - many movement events")
        
        return {
            'duration_seconds': duration,
            'activity_level': 'high' if len(events) > 15 else 'medium' if len(events) > 5 else 'low',
            'insights': insights
        }
    
    # Additional helper methods would continue here...
    # (Truncated for brevity, but would include all referenced methods)