"""
Status API - Video Processing Status

Phase 10 Implementation:

GET /videos/{video_id}/status

Returns:
    - status: uploaded | processing | processed | failed
    - progress: 0-100
    - progress_message: "Running YOLO detection (45%)"
    - frames_total: 9000
    - frames_processed: 300
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from database.session import get_db
from database.repository.video_repository import get_video_status, get_video
from database.models.video import Video

router = APIRouter(tags=["status"])


@router.get("/videos/{video_id}/status")
async def get_processing_status(
    video_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get video processing status with progress
    
    Returns current processing status including:
    - status: uploaded | processing | processed | failed
    - progress: 0-100 percentage
    - progress_message: Current step description
    - frames_total: Total frames in video
    - frames_processed: Frames processed so far
    """
    status = get_video_status(db, video_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return status


@router.get("/videos/status")
async def get_all_videos_status(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get status of all videos
    
    Returns list of all videos with their processing status
    """
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    
    return {
        "total": len(videos),
        "videos": [
            {
                "video_id": str(v.id),
                "filename": v.filename,
                "status": v.status,
                "progress": v.progress,
                "progress_message": v.progress_message,
                "frames_total": v.frames_total,
                "frames_processed": v.frames_processed,
                "created_at": v.created_at.isoformat(),
                "updated_at": v.updated_at.isoformat()
            }
            for v in videos
        ]
    }


@router.get("/videos/{video_id}/progress")
async def get_progress_percentage(
    video_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get just the progress percentage (lightweight polling endpoint)
    
    Returns:
        - progress: 0-100
        - status: processing status
    """
    video = get_video(db, video_id)
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return {
        "video_id": str(video.id),
        "filename": video.filename,
        "status": video.status,
        "progress": video.progress,
        "progress_message": video.progress_message
    }
