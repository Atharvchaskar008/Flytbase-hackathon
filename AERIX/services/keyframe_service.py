import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import cv2
from sqlalchemy.orm import Session

from backend.core.config import settings
from database.models.video import Video
from database.models.track import Track
from database.repository.keyframe_repository import create_keyframe


class KeyframeService:
    """Service for extracting and persisting important keyframes."""

    INTERESTING_EVENT_TYPES = {
        'person_entered_scene',
        'person_exited_scene',
        'started_walking',
        'stopped_moving',
        'running',
        'direction_changed',
        'loitering',
        'person_disappeared',
        'object_picked',
        'person_near_object',
        'entered_zone',
        'exited_zone',
        'object_abandoned'
    }

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.KEYFRAME_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def should_extract(self, event_type: str, metadata: dict[str, Any] | None = None) -> bool:
        if event_type in self.INTERESTING_EVENT_TYPES:
            return True
        if metadata and metadata.get('reason') in {'new_person', 'stopped', 'running', 'direction_changed', 'standing_long_time'}:
            return True
        return False

    def save_keyframe(
        self,
        db: Session,
        video: Video,
        track: Track | None,
        frame_number: int,
        timestamp: datetime,
        reason: str,
        event_type: str,
        metadata: dict[str, Any] | None,
        frame: Any | None = None,
    ):
        track_id = track.id if track else None
        camera_id = video.camera_id

        image_path = None
        if frame is not None:
            track_folder = self.output_dir / str(video.id)
            track_folder.mkdir(parents=True, exist_ok=True)
            image_filename = f"keyframe_{track_id or 'none'}_{frame_number}_{uuid.uuid4().hex[:8]}.jpg"
            image_path = str(track_folder / image_filename)
            cv2.imwrite(image_path, frame)

        return create_keyframe(
            db=db,
            video_id=video.id,
            camera_id=camera_id,
            track_id=track_id,
            frame_number=frame_number,
            timestamp=timestamp,
            reason=reason,
            image_path=image_path,
            metadata=metadata,
        )
