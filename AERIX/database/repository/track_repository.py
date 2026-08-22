import uuid
from typing import Any

from sqlalchemy.orm import Session

from database.models.track import Track


def _ensure_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def create_track(
    db: Session,
    video_id: uuid.UUID | str,
    camera_id: uuid.UUID | str,
    class_label: str = "person",
    current_position: dict[str, Any] | None = None,
    previous_position: dict[str, Any] | None = None,
    speed: float = 0.0,
    direction: str | None = None,
    duration_frames: int = 0,
    current_state: str | None = None,
) -> Track:
    track = Track(
        video_id=_ensure_uuid(video_id),
        camera_id=_ensure_uuid(camera_id),
        class_label=class_label,
        current_position=current_position or {},
        previous_position=previous_position or {},
        speed=float(speed),
        direction=direction,
        duration_frames=duration_frames,
        current_state=current_state,
    )
    db.add(track)
    db.flush()
    return track


def update_track_state(
    db: Session,
    track: Track,
    *,
    current_position: dict[str, Any] | None = None,
    previous_position: dict[str, Any] | None = None,
    speed: float | None = None,
    direction: str | None = None,
    duration_frames: int | None = None,
    current_state: str | None = None,
    last_seen: Any | None = None,
) -> Track:
    if current_position is not None:
        track.current_position = current_position
    if previous_position is not None:
        track.previous_position = previous_position
    if speed is not None:
        track.speed = float(speed)
    if direction is not None:
        track.direction = direction
    if duration_frames is not None:
        track.duration_frames = duration_frames
    if current_state is not None:
        track.current_state = current_state
    if last_seen is not None:
        track.last_seen = last_seen
    db.flush()
    return track


def get_track_by_id(db: Session, track_id: uuid.UUID | str) -> Track | None:
    if isinstance(track_id, str):
        track_id = uuid.UUID(track_id)
    return db.query(Track).filter(Track.id == track_id).first()


def list_tracks_by_video(db: Session, video_id: uuid.UUID | str) -> list[Track]:
    if isinstance(video_id, str):
        video_id = uuid.UUID(video_id)
    return db.query(Track).filter(Track.video_id == video_id).order_by(Track.first_seen.asc()).all()
