import uuid

from sqlalchemy.orm import Session

from database.models.video import Video


def create_video(
    db: Session,
    filename: str,
    file_path: str,
    status: str = "uploaded",
) -> Video:
    video = Video(filename=filename, file_path=file_path, status=status)
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def get_video(db: Session, video_id: uuid.UUID | str) -> Video | None:
    if isinstance(video_id, str):
        video_id = uuid.UUID(video_id)
    return db.query(Video).filter(Video.id == video_id).first()


def delete_video(db: Session, video_id: uuid.UUID | str) -> bool:
    if isinstance(video_id, str):
        video_id = uuid.UUID(video_id)
    video = get_video(db, video_id)
    if video is None:
        return False
    db.delete(video)
    db.commit()
    return True


def update_status(db: Session, video_id: uuid.UUID | str, status: str) -> Video | None:
    if isinstance(video_id, str):
        video_id = uuid.UUID(video_id)
    video = get_video(db, video_id)
    if video is None:
        return None
    video.status = status
    db.commit()
    db.refresh(video)
    return video


def update_progress(
    db: Session,
    video_id: uuid.UUID | str,
    progress: int,
    progress_message: str = None,
    status: str = None,
    frames_total: int = None,
    frames_processed: int = None
) -> Video | None:
    """
    Update video processing progress
    
    Args:
        db: Database session
        video_id: UUID of video
        progress: Progress percentage (0-100)
        progress_message: Current step description
        status: Optional status update
        frames_total: Total frames in video
        frames_processed: Frames processed so far
    """
    if isinstance(video_id, str):
        video_id = uuid.UUID(video_id)
    video = get_video(db, video_id)
    if video is None:
        return None
    
    video.progress = progress
    if progress_message:
        video.progress_message = progress_message
    if status:
        video.status = status
    if frames_total is not None:
        video.frames_total = frames_total
    if frames_processed is not None:
        video.frames_processed = frames_processed
    
    db.commit()
    db.refresh(video)
    return video


def get_video_status(db: Session, video_id: uuid.UUID | str) -> dict | None:
    """
    Get video processing status with progress
    
    Returns:
        Dictionary with status, progress, and metadata
    """
    video = get_video(db, video_id)
    if not video:
        return None
    
    return {
        "video_id": str(video.id),
        "filename": video.filename,
        "status": video.status,
        "progress": video.progress,
        "progress_message": video.progress_message,
        "frames_total": video.frames_total,
        "frames_processed": video.frames_processed,
        "created_at": video.created_at.isoformat(),
        "updated_at": video.updated_at.isoformat()
    }
