import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.core.logger import logger
from database.models.track import Track
from database.models.track_history import TrackHistory
from database.models.video import Video
from database.repository import event_repository, track_repository
from services.keyframe_service import KeyframeService
from services.description_service import DescriptionService

# Extended event detectors (Phase 14 extended model)
from ml_pipeline.events.dwell_time import DwellTimeDetector
from ml_pipeline.events.zone_events import ZoneEventDetector
from ml_pipeline.events.interaction_events import InteractionEventDetector


class EventIntelligenceService:
    """
    Event intelligence service for semantic track and event generation.

    Phase 7  — core movement events (entered, walked, stopped, running,
                direction_changed, exited)
    Phase 14 — keyframe extraction on interesting events
    Phase 14 extended — loitering, zone entry/exit, object interactions,
                        crowd, fall, disappearance
    """

    SPEED_STOP_THRESHOLD = 1.0
    SPEED_WALK_THRESHOLD = 5.0
    DIRECTION_CHANGE_DEGREES = 45.0

    def __init__(self, video_fps: int = 30):
        self.video_fps = video_fps
        self.track_states: dict[int, dict[str, Any]] = {}
        self.video_start_time = datetime.now()
        self.keyframe_service = KeyframeService()
        self.description_service = DescriptionService()

        # --- Extended event detectors -----------------------------------
        self.dwell_detector = DwellTimeDetector(
            loiter_seconds=30.0,
            long_stay_seconds=120.0,
            video_fps=float(video_fps),
            speed_stop_threshold=self.SPEED_STOP_THRESHOLD,
        )
        self.zone_detector = ZoneEventDetector()
        self.interaction_detector = InteractionEventDetector(
            proximity_px=80.0,
            crowd_threshold=4,
            abandoned_seconds=60.0,
            fall_aspect_ratio=2.0,
            disappeared_frames=90,
            video_fps=float(video_fps),
        )

        logger.info("Event Intelligence Service initialized (video_fps=%s)", video_fps)

    # ------------------------------------------------------------------
    # Zone setup — call once before processing a video when zones exist
    # ------------------------------------------------------------------

    def load_zones(self, camera_id: Any, db: Session) -> int:
        """
        Load zone polygons from the database for the given camera so that
        entered_zone / exited_zone events are generated during processing.

        Returns the number of zones loaded.
        """
        return self.zone_detector.load_zones_from_db(camera_id, db)

    # ------------------------------------------------------------------
    # Core event generation
    # ------------------------------------------------------------------

    def generate_events(
        self,
        tracked_objects: List[dict[str, Any]],
        lifecycle: dict[str, list[int]],
        frame_number: int,
    ) -> List[dict[str, Any]]:
        """Generate semantic events from tracked object updates."""
        events: List[dict[str, Any]] = []
        timestamp = self._calculate_timestamp(frame_number)

        # ----------------------------------------------------------------
        # 1. Movement / lifecycle events  (existing Phase 7 logic)
        # ----------------------------------------------------------------
        for track_id in lifecycle.get("new", []):
            track_obj = self._find_track_object(tracked_objects, track_id)
            if not track_obj:
                continue

            self.track_states[track_id] = {
                "track_id": track_id,
                "first_frame": frame_number,
                "last_frame": frame_number,
                "previous_position": self._format_bbox(track_obj["bbox"]),
                "current_position": self._format_bbox(track_obj["bbox"]),
                "speed": 0.0,
                "direction": None,
                "duration_frames": 0,
                "current_state": "entered_scene",
            }

            events.append(self._build_event(
                track_obj, frame_number, timestamp,
                "person_entered_scene",
                track_obj.get("confidence", 0.0),
                {
                    "class_label": track_obj.get("class_label"),
                    "current_position": self.track_states[track_id]["current_position"],
                    "previous_position": self.track_states[track_id]["previous_position"],
                    "speed": 0.0,
                    "direction": None,
                    "duration_frames": 0,
                    "current_state": "entered_scene",
                },
            ))

        for track_id in lifecycle.get("updated", []):
            track_obj = self._find_track_object(tracked_objects, track_id)
            track_state = self.track_states.get(track_id)
            if not track_obj or not track_state:
                continue

            previous_position = track_state["current_position"]
            current_position = self._format_bbox(track_obj["bbox"])
            speed = self._calculate_speed(previous_position, current_position)
            direction = self._calculate_direction(previous_position, current_position)
            duration_frames = frame_number - track_state["first_frame"]
            current_state = self._resolve_state(speed)

            state_changed = current_state != track_state["current_state"]
            direction_changed = self._has_direction_changed(track_state.get("direction"), direction)

            old_state = track_state.get("current_state")
            track_state.update({
                "last_frame": frame_number,
                "previous_position": previous_position,
                "current_position": current_position,
                "speed": speed,
                "direction": direction,
                "duration_frames": duration_frames,
                "current_state": current_state,
            })

            if direction_changed:
                events.append(self._build_event(
                    track_obj, frame_number, timestamp,
                    "direction_changed",
                    track_obj.get("confidence", 0.0),
                    {
                        "class_label": track_obj.get("class_label"),
                        "current_position": current_position,
                        "previous_position": previous_position,
                        "speed": speed,
                        "direction": direction,
                        "duration_frames": duration_frames,
                        "current_state": current_state,
                    },
                ))

            if state_changed:
                semantic_type = self._state_transition_event(old_state, current_state)
                if semantic_type:
                    events.append(self._build_event(
                        track_obj, frame_number, timestamp,
                        semantic_type,
                        track_obj.get("confidence", 0.0),
                        {
                            "class_label": track_obj.get("class_label"),
                            "current_position": current_position,
                            "previous_position": previous_position,
                            "speed": speed,
                            "direction": direction,
                            "duration_frames": duration_frames,
                            "current_state": current_state,
                        },
                    ))

            if not state_changed and not direction_changed:
                events.append(self._build_event(
                    track_obj, frame_number, timestamp,
                    current_state,
                    track_obj.get("confidence", 0.0),
                    {
                        "class_label": track_obj.get("class_label"),
                        "current_position": current_position,
                        "previous_position": previous_position,
                        "speed": speed,
                        "direction": direction,
                        "duration_frames": duration_frames,
                        "current_state": current_state,
                    },
                ))

            # --------------------------------------------------------
            # 2a. Dwell / loitering events  (per updated track)
            # --------------------------------------------------------
            dwell_events = self.dwell_detector.update(
                track_id=track_id,
                frame_number=frame_number,
                timestamp=timestamp,
                speed=speed,
                position=current_position,
                confidence=float(track_obj.get("confidence", 1.0)),
            )
            events.extend(dwell_events)

            # --------------------------------------------------------
            # 2b. Zone entry / exit events  (per updated track)
            # --------------------------------------------------------
            zone_events = self.zone_detector.update(
                track_id=track_id,
                frame_number=frame_number,
                timestamp=timestamp,
                position=current_position,
                confidence=float(track_obj.get("confidence", 1.0)),
            )
            events.extend(zone_events)

        for track_id in lifecycle.get("lost", []):
            track_state = self.track_states.pop(track_id, None)
            if not track_state:
                continue

            events.append({
                "event_type": "person_exited_scene",
                "track_id": track_id,
                "frame_number": frame_number,
                "confidence": 0.0,
                "timestamp": timestamp,
                "metadata": {
                    "class_label": "person",
                    "last_position": track_state.get("current_position"),
                    "previous_position": track_state.get("previous_position"),
                    "duration_frames": track_state.get("duration_frames", 0),
                    "current_state": track_state.get("current_state"),
                },
            })

            # Clean up extended detector state for lost tracks
            self.dwell_detector.remove_track(track_id)
            self.zone_detector.remove_track(track_id)
            # Normal exit — no person_disappeared event needed
            self.interaction_detector.remove_track(track_id, frame_number, timestamp, normal_exit=True)

        # ----------------------------------------------------------------
        # 3. Frame-level interaction events  (crowd, fall, object proximity,
        #    object abandoned, person_near_object, picked/left)
        # ----------------------------------------------------------------
        interaction_events = self.interaction_detector.update_frame(
            frame_number=frame_number,
            timestamp=timestamp,
            tracked_objects=tracked_objects,
        )
        events.extend(interaction_events)

        return events

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist_frame_data(
        self,
        db: Session,
        video: Video,
        tracked_objects: List[dict[str, Any]],
        events: List[dict[str, Any]],
        all_tracks: dict[int, Track],
        frame_number: int,
        frame: Any | None = None,
    ) -> None:
        """Persist track history, events, keyframes, and descriptions for the current frame."""
        for obj in tracked_objects:
            track_id = obj["track_id"]
            if track_id not in all_tracks:
                track = track_repository.create_track(
                    db=db,
                    video_id=video.id,
                    camera_id=video.camera_id,
                    class_label=obj.get("class_label", "person"),
                    current_position=self._format_bbox(obj["bbox"]),
                    previous_position=self._format_bbox(obj["bbox"]),
                    speed=0.0,
                    direction=None,
                    duration_frames=0,
                    current_state="entered_scene",
                )
                all_tracks[track_id] = track
            else:
                track = all_tracks[track_id]

            track_state = self.track_states.get(track_id)
            if track_state is not None:
                track_repository.update_track_state(
                    db=db,
                    track=track,
                    current_position=track_state.get("current_position"),
                    previous_position=track_state.get("previous_position"),
                    speed=track_state.get("speed"),
                    direction=track_state.get("direction"),
                    duration_frames=track_state.get("duration_frames"),
                    current_state=track_state.get("current_state"),
                    last_seen=datetime.now(),
                )

            bbox = obj["bbox"]
            track_history = TrackHistory(
                track_id=track.id,
                frame_number=obj.get("frame_number", frame_number),
                bbox_x=float(bbox[0]),
                bbox_y=float(bbox[1]),
                bbox_w=float(bbox[2]),
                bbox_h=float(bbox[3]),
                confidence=float(obj.get("confidence", 0.0)),
            )
            db.add(track_history)

        for event_data in events:
            track_model = all_tracks.get(event_data.get("track_id"))
            event_repository.create_event(
                db=db,
                track_id=track_model.id if track_model else None,
                camera_id=video.camera_id,
                video_id=video.id,
                event_type=event_data["event_type"],
                score=float(event_data.get("confidence", 0.0)),
                metadata=event_data.get("metadata", {}),
                timestamp=event_data["timestamp"],
                frame_number=event_data["frame_number"],
            )

            if self.keyframe_service.should_extract(event_data["event_type"], event_data.get("metadata")):
                keyframe = self.keyframe_service.save_keyframe(
                    db=db,
                    video=video,
                    track=track_model,
                    frame_number=event_data["frame_number"],
                    timestamp=event_data["timestamp"],
                    reason=event_data["event_type"],
                    event_type=event_data["event_type"],
                    metadata=event_data.get("metadata", {}),
                    frame=frame,
                )
                self.description_service.create_description_for_keyframe(
                    db=db,
                    keyframe=keyframe,
                    event_type=event_data["event_type"],
                    metadata=event_data.get("metadata", {}),
                )

    # ------------------------------------------------------------------
    # Utility methods (unchanged)
    # ------------------------------------------------------------------

    def _build_event(
        self,
        track_obj: dict[str, Any],
        frame_number: int,
        timestamp: datetime,
        event_type: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "track_id": track_obj.get("track_id"),
            "frame_number": frame_number,
            "confidence": float(confidence),
            "timestamp": timestamp,
            "metadata": metadata,
        }

    def _find_track_object(self, tracked_objects: List[dict[str, Any]], track_id: int) -> Optional[dict[str, Any]]:
        return next((obj for obj in tracked_objects if obj.get("track_id") == track_id), None)

    def _calculate_timestamp(self, frame_number: int) -> datetime:
        seconds = frame_number / self.video_fps
        return self.video_start_time + timedelta(seconds=seconds)

    def _format_bbox(self, bbox: list[float]) -> dict[str, float]:
        x, y, w, h = bbox
        return {
            "x": float(x),
            "y": float(y),
            "w": float(w),
            "h": float(h),
            "center_x": float(x + w / 2),
            "center_y": float(y + h / 2),
        }

    def _calculate_speed(self, previous_position: dict[str, Any], current_position: dict[str, Any]) -> float:
        if not previous_position or not current_position:
            return 0.0
        dx = current_position["center_x"] - previous_position["center_x"]
        dy = current_position["center_y"] - previous_position["center_y"]
        return math.hypot(dx, dy)

    def _calculate_direction(self, previous_position: dict[str, Any], current_position: dict[str, Any]) -> Optional[str]:
        if not previous_position or not current_position:
            return None
        dx = current_position["center_x"] - previous_position["center_x"]
        dy = current_position["center_y"] - previous_position["center_y"]
        if dx == 0 and dy == 0:
            return None
        angle = math.degrees(math.atan2(dy, dx))
        if abs(angle) <= 45:
            return "east"
        if abs(angle) >= 135:
            return "west"
        return "south" if angle > 0 else "north"

    def _resolve_state(self, speed: float) -> str:
        if speed < self.SPEED_STOP_THRESHOLD:
            return "standing"
        if speed < self.SPEED_WALK_THRESHOLD:
            return "walking"
        return "running"

    def _state_transition_event(self, previous_state: str | None, next_state: str) -> Optional[str]:
        if previous_state in {None, "entered_scene"} and next_state == "walking":
            return "started_walking"
        if previous_state in {"walking", "running"} and next_state == "standing":
            return "stopped_moving"
        if next_state == "running":
            return "running"
        if next_state == "standing":
            return "standing"
        return None

    def _has_direction_changed(self, previous_direction: Optional[str], current_direction: Optional[str]) -> bool:
        if not previous_direction or not current_direction:
            return False
        return previous_direction != current_direction
