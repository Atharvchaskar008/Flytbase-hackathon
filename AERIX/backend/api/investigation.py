"""
Investigation API - Unified Search Interface

Phase 11 Implementation:

One endpoint returns everything:
- Timeline
- Events
- Tracks
- Clips

Usage:
    POST /investigate/search
    GET /investigate/video/{video_id}
    GET /investigate/track/{track_id}
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime

from database.session import get_db
from services.investigation_service import InvestigationService, investigate

router = APIRouter(prefix="/investigate", tags=["investigation"])


@router.post("/search")
async def search_investigation(
    query: str = Query(..., description="Search query (e.g., 'red cap')"),
    video_id: Optional[str] = Query(None, description="Filter by video ID"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    start_time: Optional[datetime] = Query(None, description="Start time filter"),
    end_time: Optional[datetime] = Query(None, description="End time filter"),
    limit: int = Query(50, description="Maximum results"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Unified search endpoint
    
    Returns timeline, events, tracks, and clips in one response.
    
    Example:
        POST /investigate/search?query=red cap&video_id=uuid
        
    Returns:
        {
            "query": "red cap",
            "summary": {
                "total_events": 150,
                "total_tracks": 5,
                "timeline_entries": 150
            },
            "timeline": [...],
            "events": [...],
            "tracks": [...],
            "clips": [...]
        }
    """
    service = InvestigationService(db)
    
    return service.search(
        query=query,
        video_id=video_id,
        camera_id=camera_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )


@router.get("/video/{video_id}")
async def investigate_video(
    video_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get complete investigation results for a video
    
    Returns:
        - Video information with processing status
        - Timeline of all events
        - All tracks with summaries
        - Summary statistics
    """
    service = InvestigationService(db)
    return service.investigate_video(video_id)


@router.get("/track/{track_id}")
async def investigate_track(
    track_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get complete investigation results for a track
    
    Returns:
        - Track information
        - Timeline of track events
        - Video and camera details
        - Clip links
    """
    service = InvestigationService(db)
    return service.investigate_track(track_id)


@router.get("/person/{timestamp}")
async def find_person_by_time(
    timestamp: datetime,
    camera_id: Optional[str] = Query(None),
    time_window: int = Query(30, description="Time window in seconds"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Find persons visible at a specific time
    
    Returns all tracks active at the given timestamp.
    """
    service = InvestigationService(db)
    return service.find_person_by_time(
        timestamp=timestamp,
        camera_id=camera_id,
        time_window_seconds=time_window
    )
