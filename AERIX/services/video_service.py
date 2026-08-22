import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.logger import logger
from database.repository import video_repository


class VideoService:
    def upload_video(self, db: Session, file: UploadFile) -> dict:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required",
            )

        extension = Path(file.filename).suffix.lower()
        if extension not in settings.ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {extension}",
            )

        # Validate size using size attribute if present
        if getattr(file, "size", None) is not None and file.size > settings.MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum size of {settings.MAX_VIDEO_SIZE} bytes",
            )

        settings.VIDEO_DIR.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4()}{extension}"
        destination = settings.VIDEO_DIR / stored_name

        try:
            total_bytes = 0
            with destination.open("wb") as buffer:
                while chunk := file.file.read(1024 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > settings.MAX_VIDEO_SIZE:
                        buffer.close()
                        if destination.exists():
                            destination.unlink()
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"File exceeds maximum size of {settings.MAX_VIDEO_SIZE} bytes",
                        )
                    buffer.write(chunk)
        except OSError as exc:
            logger.error("Failed to save uploaded video: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save uploaded video",
            ) from exc

        video = video_repository.create_video(
            db=db,
            filename=file.filename,
            file_path=str(destination),
            status="uploaded",
        )
        
        # Set default camera_id if not set
        if not video.camera_id:
            import uuid
            default_camera_id = uuid.UUID('a0000000-0000-0000-0000-000000000001')
            video.camera_id = default_camera_id
            db.commit()
            db.refresh(video)

        return {
            "id": str(video.id),
            "video_id": str(video.id),
            "filename": video.filename,
            "file_path": video.file_path,
            "status": video.status,
        }

