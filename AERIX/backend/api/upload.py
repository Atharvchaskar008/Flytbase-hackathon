from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from database.session import get_db
from services.video_service import VideoService
from ml_pipeline.orchestrator import process_video
from database.models.video import Video

router = APIRouter(prefix="/upload", tags=["upload"])
video_service = VideoService()


@router.post("/video")
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return video_service.upload_video(db, file)


@router.post("/process/{video_id}")
async def process_video_endpoint(
    video_id: str,
    traffic_mode: bool = True,
    sample_rate: int = 3,
    confidence_threshold: float = 0.3,
    db: Session = Depends(get_db),
):
    """
    Process video through the ML pipeline
    
    Args:
        video_id: UUID of uploaded video
        traffic_mode: Whether to run traffic detection & tracking (Level 1)
        sample_rate: Process every Nth frame (default 3)
        confidence_threshold: Min detection confidence (default 0.3)
        db: Database session
        
    Returns:
        Processing status and summary
    """
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

        if traffic_mode:
            from ml_pipeline.traffic_pipeline import process_traffic_video
            result = process_traffic_video(
                video_path=video.file_path,
                sample_rate=sample_rate,
                confidence_threshold=confidence_threshold,
                use_real_yolo=False,  # Fall back to real YOLO inside process_traffic_video if available
            )
            return result
        else:
            config = {
                'sample_rate': sample_rate,
                'use_real_yolo': False,
                'use_real_models': False,
                'generate_reid_embeddings': True,
                'generate_clip_embeddings': True
            }
            result = process_video(video_id, db, config=config)
            return {
                "status": "success",
                "video_id": video_id,
                "message": "Video processed successfully"
            }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")



@router.get("/videos")
async def list_videos(
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get list of all uploaded videos
    
    Returns:
        List of videos with their details
    """
    videos = db.query(Video).order_by(Video.created_at.desc()).all()
    
    return [
        {
            "id": str(video.id),
            "filename": video.filename,
            "file_path": video.file_path,
            "status": video.status,
            "duration_seconds": video.duration_seconds,
            "created_at": video.created_at.isoformat(),
            "updated_at": video.updated_at.isoformat()
        }
        for video in videos
    ]
