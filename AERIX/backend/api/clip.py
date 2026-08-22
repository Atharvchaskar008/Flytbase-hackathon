"""
Phase 12: Clip Retrieval API

GET /clip/{event_id}

Input: Event ID
↓
Find timestamp
↓
Locate original video
↓
FFmpeg
↓
Extract ±15–30 seconds
↓
Return clip.mp4
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
from pathlib import Path

from database.session import get_db
from services.clip_service import ClipService

router = APIRouter(prefix="/clip", tags=["clip"])
clip_service = ClipService()


@router.get("/{event_id}")
async def get_event_clip(
    event_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get video clip for an event (Phase 12)
    
    Workflow:
    Event ID → Find timestamp → Locate video → FFmpeg → Extract ±15s → Return URL
    
    Args:
        event_id: UUID of the event
        db: Database session
        
    Returns:
        Dictionary with clip URL and metadata
        
    Raises:
        HTTPException: If event not found or clip extraction fails
    """
    result = clip_service.extract_clip(event_id, db)
    return result


@router.get("/{event_id}/download")
async def download_event_clip(
    event_id: str,
    db: Session = Depends(get_db)
) -> FileResponse:
    """
    Download video clip for an event
    
    Args:
        event_id: UUID of the event
        db: Database session
        
    Returns:
        FileResponse with the video clip
        
    Raises:
        HTTPException: If event not found or clip extraction fails
    """
    result = clip_service.extract_clip(event_id, db)
    clip_path = Path(result["clip_path"])
    
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found")
    
    return FileResponse(
        path=str(clip_path),
        media_type="video/mp4",
        filename=clip_path.name
    )
