import uuid
from typing import Any, Dict, List
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.logger import logger
from database.models.event import Event
from database.models.track import Track
from database.models.video import Video
from services.timeline_builder import TimelineBuilder


class TimelineService:
    """Service layer for video timeline and event retrieval."""

    def __init__(self, video_fps: int = 30):
        self.video_fps = video_fps
        self.builder = TimelineBuilder(video_fps=video_fps)
        logger.info("TimelineService initialized (video_fps=%s)", video_fps)

    def _parse_uuid(self, value: str) -> uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            logger.error("Invalid UUID provided: %s", value)
            raise

    def get_video_timeline(self, video_id: str, db: Session) -> List[Dict[str, Any]]:
        video_uuid = self._parse_uuid(video_id)

        video = db.query(Video).filter(Video.id == video_uuid).first()
        if not video:
            raise ValueError("Video not found")

        events = (
            db.query(Event)
            .filter(Event.video_id == video_uuid)
            .order_by(Event.timestamp.asc())
            .all()
        )

        return [
            {
                "id": str(event.id),
                "track_id": str(event.track_id) if event.track_id else None,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "time": event.timestamp.strftime("%H:%M:%S"),
                "frame_number": event.frame_number,
                "confidence": event.score,
                "metadata": event.event_metadata or {},
            }
            for event in events
        ]

    def get_video_timeline_summary(self, video_id: str, db: Session) -> Dict[str, Any]:
        video_uuid = self._parse_uuid(video_id)

        video = db.query(Video).filter(Video.id == video_uuid).first()
        if not video:
            raise ValueError("Video not found")

        event_counts = (
            db.query(Event.event_type, func.count(Event.id))
            .filter(Event.video_id == video_uuid)
            .group_by(Event.event_type)
            .all()
        )

        total_tracks = (
            db.query(Track)
            .filter(Track.video_id == video_uuid)
            .count()
        )

        first_event = (
            db.query(Event)
            .filter(Event.video_id == video_uuid)
            .order_by(Event.timestamp.asc())
            .first()
        )

        last_event = (
            db.query(Event)
            .filter(Event.video_id == video_uuid)
            .order_by(Event.timestamp.desc())
            .first()
        )

        timeline_duration = None
        if first_event and last_event:
            duration_seconds = (last_event.timestamp - first_event.timestamp).total_seconds()
            timeline_duration = f"{int(duration_seconds // 60):02d}:{int(duration_seconds % 60):02d}"

        return {
            "video_id": video_id,
            "video_status": video.status,
            "total_tracks": total_tracks,
            "total_events": sum(count for _, count in event_counts),
            "events_by_type": {event_type: count for event_type, count in event_counts},
            "timeline_duration": timeline_duration,
            "first_event": first_event.timestamp.isoformat() if first_event else None,
            "last_event": last_event.timestamp.isoformat() if last_event else None,
        }

    def get_video_tracks(self, video_id: str, db: Session) -> List[Dict[str, Any]]:
        video_uuid = self._parse_uuid(video_id)

        video = db.query(Video).filter(Video.id == video_uuid).first()
        if not video:
            raise ValueError("Video not found")

        tracks = (
            db.query(Track)
            .filter(Track.video_id == video_uuid)
            .order_by(Track.first_seen.asc())
            .all()
        )

        return [
            {
                "track_id": str(track.id),
                "class_label": track.class_label,
                "first_seen": track.first_seen.isoformat(),
                "last_seen": track.last_seen.isoformat() if track.last_seen else None,
                "current_position": track.current_position or {},
                "previous_position": track.previous_position or {},
                "speed": track.speed,
                "direction": track.direction,
                "duration_frames": track.duration_frames,
                "current_state": track.current_state,
                "reid_global_id": track.reid_global_id,
            }
            for track in tracks
        ]

    def get_video_events(self, video_id: str, db: Session) -> List[Dict[str, Any]]:
        video_uuid = self._parse_uuid(video_id)

        video = db.query(Video).filter(Video.id == video_uuid).first()
        if not video:
            raise ValueError("Video not found")

        events = (
            db.query(Event)
            .filter(Event.video_id == video_uuid)
            .order_by(Event.timestamp.asc())
            .all()
        )

        return [
            {
                "id": str(event.id),
                "track_id": str(event.track_id) if event.track_id else None,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "frame_number": event.frame_number,
                "confidence": event.score,
                "metadata": event.event_metadata or {},
            }
            for event in events
        ]
