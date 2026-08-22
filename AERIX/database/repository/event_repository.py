import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from database.models.event import Event


def _ensure_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def create_event(
    db: Session,
    *,
    track_id: uuid.UUID | str | None,
    camera_id: uuid.UUID | str,
    video_id: uuid.UUID | str,
    event_type: str,
    score: float,
    metadata: dict[str, Any] | None,
    timestamp: datetime,
    frame_number: int,
) -> Event:
    """Create a new event record without committing the session."""
    event = Event(
        track_id=_ensure_uuid(track_id),
        camera_id=_ensure_uuid(camera_id),
        video_id=_ensure_uuid(video_id),
        event_type=event_type,
        score=float(score) if score is not None else 0.0,
        event_metadata=metadata or {},
        timestamp=timestamp,
        frame_number=frame_number,
    )
    db.add(event)
    return event


def list_events_by_video(db: Session, video_id: uuid.UUID | str) -> list[Event]:
    if isinstance(video_id, str):
        video_id = uuid.UUID(video_id)
    return db.query(Event).filter(Event.video_id == video_id).order_by(Event.timestamp.asc()).all()


def list_events_by_track(db: Session, track_id: uuid.UUID | str) -> list[Event]:
    if isinstance(track_id, str):
        track_id = uuid.UUID(track_id)
    return db.query(Event).filter(Event.track_id == track_id).order_by(Event.timestamp.asc()).all()
