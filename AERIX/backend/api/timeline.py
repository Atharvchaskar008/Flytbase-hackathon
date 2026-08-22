"""
Timeline API - Phase 9 Implementation
GET /videos/{id}/timeline

Flow:
Video ID → Fetch Events → Sort by Timestamp → Return JSON
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from database.session import get_db
from services.timeline_service import TimelineService

router = APIRouter()

timeline_service = TimelineService()


@router.get("/videos/{video_id}/timeline")
async def get_video_timeline(
    video_id: str,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get timeline of events for a video."""
    try:
        return timeline_service.get_video_timeline(video_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get video timeline: {exc}")


@router.get("/videos/{video_id}/timeline/summary")
async def get_video_timeline_summary(
    video_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get summary statistics for video timeline."""
    try:
        return timeline_service.get_video_timeline_summary(video_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get timeline summary: {exc}")


@router.get("/videos/{video_id}/tracks")
async def get_video_tracks(
    video_id: str,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get all tracks for a video."""
    try:
        return timeline_service.get_video_tracks(video_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get video tracks: {exc}")


@router.get("/videos/{video_id}/events")
async def get_video_events(
    video_id: str,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get all events for a video."""
    try:
        return timeline_service.get_video_events(video_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get video events: {exc}")


@router.get("/videos/{video_id}/tracks")
async def get_video_tracks(
    video_id: str,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get all tracks for a video with their basic information
    
    Args:
        video_id: UUID of the video
        db: Database session
        
    Returns:
        List of tracks with their information
    """
    
    try:
        return timeline_service.get_video_tracks(video_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get video tracks: {exc}")
    
    tracks_info = []
    for track in tracks:
        # Count events for this track
        event_count = (
            db.query(Event)
            .filter(Event.track_id == track.id)
            .count()
        )
        
        track_info = {
            "track_id": str(track.id),
            "class_label": track.class_label,
            "first_seen": track.first_seen.isoformat(),
            "last_seen": track.last_seen.isoformat() if track.last_seen else None,
            "event_count": event_count,
            "reid_global_id": track.reid_global_id
        }
        
        tracks_info.append(track_info)
    
    return tracks_info



@router.get("/videos/{video_id}/events")
async def get_video_events(
    video_id: str,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get all events for a video
    
    Args:
        video_id: UUID of the video
        db: Database session
        
    Returns:
        List of events with their details
    """
    
    try:
        return timeline_service.get_video_events(video_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get video events: {exc}")
        event_data = {
            "id": str(event.id),
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "score": event.score,
            "track_id": str(track.id) if track else None,
            "class_label": track.class_label if track else None,
            "metadata": event.event_metadata or {}
        }
        events_list.append(event_data)
    
    return events_list
