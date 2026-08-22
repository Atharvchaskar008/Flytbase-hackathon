import uuid
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session

from database.models.description import Description


def _ensure_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def create_description(
    db: Session,
    *,
    track_id: uuid.UUID | str | None,
    keyframe_id: uuid.UUID | str | None,
    video_id: uuid.UUID | str | None,
    frame_number: int,
    timestamp: datetime,
    description: str,
    objects: list[str] | None = None,
    confidence: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> Description:
    description_record = Description(
        track_id=_ensure_uuid(track_id),
        keyframe_id=_ensure_uuid(keyframe_id),
        video_id=_ensure_uuid(video_id),
        frame_number=frame_number,
        timestamp=timestamp,
        description=description,
        objects=objects or [],
        confidence=float(confidence),
        desc_metadata=metadata or {},
    )
    db.add(description_record)
    db.flush()
    return description_record


def list_descriptions_by_track(db: Session, track_id: uuid.UUID | str, limit: int = 100) -> list[Description]:
    if isinstance(track_id, str):
        track_id = uuid.UUID(track_id)
    return db.query(Description).filter(Description.track_id == track_id).order_by(Description.timestamp.asc()).limit(limit).all()


def search_descriptions(db: Session, query: str, max_results: int = 50) -> list[Description]:
    return (
        db.query(Description)
        .filter(Description.description.ilike(f"%{query}%"))
        .order_by(Description.confidence.desc())
        .limit(max_results)
        .all()
    )
