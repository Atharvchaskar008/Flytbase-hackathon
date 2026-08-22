import uuid
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session

from database.models.keyframe import Keyframe


def _ensure_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def create_keyframe(
    db: Session,
    *,
    video_id: uuid.UUID | str | None,
    camera_id: uuid.UUID | str | None,
    track_id: uuid.UUID | str | None,
    frame_number: int,
    timestamp: datetime,
    reason: str,
    image_path: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Keyframe:
    keyframe = Keyframe(
        video_id=_ensure_uuid(video_id),
        camera_id=_ensure_uuid(camera_id),
        track_id=_ensure_uuid(track_id),
        frame_number=frame_number,
        timestamp=timestamp,
        reason=reason,
        image_path=image_path,
        keyframe_metadata=metadata or {},
    )
    db.add(keyframe)
    db.flush()
    return keyframe


def list_keyframes_by_video(db: Session, video_id: uuid.UUID | str, limit: int = 100) -> list[Keyframe]:
    if isinstance(video_id, str):
        video_id = uuid.UUID(video_id)
    return db.query(Keyframe).filter(Keyframe.video_id == video_id).order_by(Keyframe.timestamp.asc()).limit(limit).all()
