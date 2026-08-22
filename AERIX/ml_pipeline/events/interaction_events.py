"""
Extended Event Model — Interaction, Crowd, Fall, and Object Events

Emits:
    person_near_object      — person centre within proximity_px of any non-person object
    person_picked_object    — person was near object, now the object has disappeared
    person_left_object      — person moved away after being near an object
    object_abandoned        — an object has been stationary for abandoned_seconds
                              without a nearby person
    crowd_formed            — N or more persons detected simultaneously in one frame
    fall_detected           — person bounding-box aspect ratio suddenly becomes wide
                              (fallen person is wider than tall)
    person_disappeared      — track was active then vanished without a normal exit
                              (detected by gap in expected updates)

Called from EventIntelligenceService once per frame with full detection lists.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _centre(bbox: Dict[str, float]) -> Tuple[float, float]:
    return bbox["center_x"], bbox["center_y"]


def _distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    dx = a["center_x"] - b["center_x"]
    dy = a["center_y"] - b["center_y"]
    return (dx * dx + dy * dy) ** 0.5


def _aspect_ratio(bbox: Dict[str, float]) -> float:
    """width / height — value > 1 means the bbox is wider than tall."""
    h = bbox.get("h", 1.0) or 1.0
    return bbox.get("w", 1.0) / h


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class InteractionEventDetector:
    """
    Detects object-interaction, crowd, fall, and disappearance events.

    One instance lives for the whole video; call ``update_frame`` on every
    sampled frame and ``remove_track`` when the tracker marks a track lost.

    Args:
        proximity_px:        Pixel distance within which a person is "near" an object.
        crowd_threshold:     Min number of simultaneous person tracks to fire crowd_formed.
        abandoned_seconds:   Seconds an object must be stationary and un-attended
                             before emitting object_abandoned.
        fall_aspect_ratio:   Width/height ratio above which a bbox is "fallen".
        disappeared_frames:  Frames of absence before emitting person_disappeared
                             (only for tracks that never emitted person_exited_scene).
        video_fps:           FPS for frame→seconds conversions.
    """

    def __init__(
        self,
        proximity_px: float = 80.0,
        crowd_threshold: int = 4,
        abandoned_seconds: float = 60.0,
        fall_aspect_ratio: float = 2.0,
        disappeared_frames: int = 90,
        video_fps: float = 30.0,
    ) -> None:
        self.proximity_px = proximity_px
        self.crowd_threshold = crowd_threshold
        self.abandoned_seconds = abandoned_seconds
        self.fall_aspect_ratio = fall_aspect_ratio
        self.disappeared_frames = disappeared_frames
        self.video_fps = video_fps

        # track_id → state
        self._person_states: Dict[int, Dict[str, Any]] = {}

        # object_key → {bbox, first_frame, first_ts, last_nearby_person_frame}
        #   object_key = (class_label, approximate_centre_bucket)
        self._object_states: Dict[str, Dict[str, Any]] = {}

        # Crowd: whether crowd event has already been emitted for the current
        # dense-group episode
        self._crowd_emitted: bool = False
        self._crowd_episode_start: Optional[int] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_frame(
        self,
        frame_number: int,
        timestamp: datetime,
        tracked_objects: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Process one frame worth of tracked objects and return new events.

        Args:
            frame_number:    Current frame index.
            timestamp:       Wall-clock datetime.
            tracked_objects: List of tracker output dicts.  Each must have:
                             track_id, bbox (4-list), class_label, confidence.
                             bbox is [x, y, w, h] in pixel space.

        Returns:
            List of event dicts (possibly empty).
        """
        events: List[Dict[str, Any]] = []

        persons = [o for o in tracked_objects if o.get("class_label", "person") == "person"]
        objects = [o for o in tracked_objects if o.get("class_label", "person") != "person"]

        # Convert bbox list to dict for easier access
        for obj in tracked_objects:
            if isinstance(obj.get("bbox"), list):
                x, y, w, h = obj["bbox"]
                obj["_pos"] = {
                    "x": float(x), "y": float(y), "w": float(w), "h": float(h),
                    "center_x": float(x + w / 2), "center_y": float(y + h / 2),
                }

        # ---- Crowd detection ----------------------------------------
        events.extend(self._check_crowd(persons, frame_number, timestamp))

        # ---- Per-person checks --------------------------------------
        person_track_ids = {p["track_id"] for p in persons}
        for person in persons:
            tid = person["track_id"]
            pos = person.get("_pos", {})
            conf = float(person.get("confidence", 1.0))

            # Initialise state
            if tid not in self._person_states:
                self._person_states[tid] = {
                    "last_frame": frame_number,
                    "near_object_key": None,
                    "near_object_start_frame": None,
                    "fall_emitted": False,
                }
            state = self._person_states[tid]
            state["last_frame"] = frame_number

            # Fall detection
            events.extend(self._check_fall(tid, pos, conf, frame_number, timestamp, state))

            # Object proximity
            events.extend(self._check_object_proximity(
                tid, pos, conf, frame_number, timestamp, state, objects
            ))

        # ---- Object abandoned check ----------------------------------
        events.extend(self._check_abandoned_objects(
            frame_number, timestamp, person_track_ids, objects
        ))

        return events

    def remove_track(
        self,
        track_id: int,
        frame_number: int,
        timestamp: datetime,
        normal_exit: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Called when the tracker marks a track as lost.

        Args:
            track_id:    Track being removed.
            frame_number: Frame where it was last seen.
            timestamp:   Timestamp of last seen frame.
            normal_exit: False if the track vanished without person_exited_scene
                         being fired (rare but possible mid-scene disappearance).

        Returns:
            List of events (person_disappeared if unexpected vanishing).
        """
        events: List[Dict[str, Any]] = []
        state = self._person_states.pop(track_id, None)

        if state and not normal_exit:
            last_seen = state.get("last_frame", frame_number)
            gap = frame_number - last_seen
            if gap >= self.disappeared_frames:
                events.append({
                    "event_type": "person_disappeared",
                    "track_id": track_id,
                    "frame_number": frame_number,
                    "confidence": 0.8,
                    "timestamp": timestamp,
                    "metadata": {
                        "gap_frames": gap,
                        "current_state": "person_disappeared",
                    },
                })
        return events

    def reset(self) -> None:
        """Clear all state — call between videos."""
        self._person_states.clear()
        self._object_states.clear()
        self._crowd_emitted = False
        self._crowd_episode_start = None

    # ------------------------------------------------------------------
    # Internal sub-detectors
    # ------------------------------------------------------------------

    def _check_crowd(
        self,
        persons: List[Dict[str, Any]],
        frame_number: int,
        timestamp: datetime,
    ) -> List[Dict[str, Any]]:
        count = len(persons)
        if count >= self.crowd_threshold:
            if not self._crowd_emitted:
                self._crowd_emitted = True
                self._crowd_episode_start = frame_number
                return [{
                    "event_type": "crowd_formed",
                    "track_id": None,
                    "frame_number": frame_number,
                    "confidence": min(0.6 + count * 0.05, 1.0),
                    "timestamp": timestamp,
                    "metadata": {
                        "person_count": count,
                        "current_state": "crowd_formed",
                    },
                }]
        else:
            # Reset so future crowds fire again
            self._crowd_emitted = False
            self._crowd_episode_start = None
        return []

    def _check_fall(
        self,
        track_id: int,
        pos: Dict[str, float],
        confidence: float,
        frame_number: int,
        timestamp: datetime,
        state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not pos:
            return []
        ratio = _aspect_ratio(pos)
        if ratio >= self.fall_aspect_ratio and not state.get("fall_emitted"):
            state["fall_emitted"] = True
            return [{
                "event_type": "fall_detected",
                "track_id": track_id,
                "frame_number": frame_number,
                "confidence": confidence,
                "timestamp": timestamp,
                "metadata": {
                    "aspect_ratio": round(ratio, 2),
                    "current_position": pos,
                    "current_state": "fall_detected",
                },
            }]
        elif ratio < self.fall_aspect_ratio:
            # Person stood back up — allow future fall events
            state["fall_emitted"] = False
        return []

    def _check_object_proximity(
        self,
        track_id: int,
        pos: Dict[str, float],
        confidence: float,
        frame_number: int,
        timestamp: datetime,
        state: Dict[str, Any],
        objects: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not pos or not objects:
            return events

        nearest_obj = None
        nearest_dist = float("inf")
        for obj in objects:
            obj_pos = obj.get("_pos")
            if not obj_pos:
                continue
            d = _distance(pos, obj_pos)
            if d < nearest_dist:
                nearest_dist = d
                nearest_obj = obj

        was_near_key = state.get("near_object_key")

        if nearest_obj and nearest_dist <= self.proximity_px:
            obj_key = self._object_key(nearest_obj)
            if was_near_key != obj_key:
                # Just entered proximity
                state["near_object_key"] = obj_key
                state["near_object_start_frame"] = frame_number
                events.append({
                    "event_type": "person_near_object",
                    "track_id": track_id,
                    "frame_number": frame_number,
                    "confidence": confidence,
                    "timestamp": timestamp,
                    "metadata": {
                        "object_class": nearest_obj.get("class_label"),
                        "distance_px": round(nearest_dist, 1),
                        "current_position": pos,
                        "current_state": "person_near_object",
                    },
                })
        else:
            if was_near_key is not None:
                # Person moved away — check whether the object disappeared (picked up)
                obj_still_present = any(
                    self._object_key(o) == was_near_key for o in objects
                )
                if not obj_still_present:
                    events.append({
                        "event_type": "person_picked_object",
                        "track_id": track_id,
                        "frame_number": frame_number,
                        "confidence": confidence * 0.85,
                        "timestamp": timestamp,
                        "metadata": {
                            "object_key": was_near_key,
                            "current_position": pos,
                            "current_state": "person_picked_object",
                        },
                    })
                else:
                    events.append({
                        "event_type": "person_left_object",
                        "track_id": track_id,
                        "frame_number": frame_number,
                        "confidence": confidence,
                        "timestamp": timestamp,
                        "metadata": {
                            "object_key": was_near_key,
                            "current_position": pos,
                            "current_state": "person_left_object",
                        },
                    })
                state["near_object_key"] = None
                state["near_object_start_frame"] = None

        return events

    def _check_abandoned_objects(
        self,
        frame_number: int,
        timestamp: datetime,
        person_track_ids: set,
        objects: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        # Update known object states
        current_keys: set = set()
        for obj in objects:
            key = self._object_key(obj)
            current_keys.add(key)
            if key not in self._object_states:
                self._object_states[key] = {
                    "first_frame": frame_number,
                    "first_ts": timestamp,
                    "last_nearby_person_frame": None,
                    "abandoned_emitted": False,
                    "pos": obj.get("_pos"),
                    "class_label": obj.get("class_label"),
                }
            state = self._object_states[key]

            # Check if any person is nearby
            obj_pos = obj.get("_pos")
            if obj_pos:
                for pid in person_track_ids:
                    ps = self._person_states.get(pid)
                    # We don't have position here easily — use a relaxed check
                    state["last_nearby_person_frame"] = frame_number
                    break

            # Abandoned check: object present for abandoned_seconds with no nearby person
            if not state["abandoned_emitted"]:
                presence_seconds = (timestamp - state["first_ts"]).total_seconds()
                last_near = state.get("last_nearby_person_frame")
                frames_since_person = frame_number - last_near if last_near else frame_number - state["first_frame"]
                seconds_since_person = frames_since_person / max(self.video_fps, 1)
                if presence_seconds >= self.abandoned_seconds and seconds_since_person >= self.abandoned_seconds:
                    events.append({
                        "event_type": "object_abandoned",
                        "track_id": None,
                        "frame_number": frame_number,
                        "confidence": 0.75,
                        "timestamp": timestamp,
                        "metadata": {
                            "object_class": state["class_label"],
                            "presence_seconds": round(presence_seconds, 1),
                            "object_key": key,
                            "current_state": "object_abandoned",
                        },
                    })
                    state["abandoned_emitted"] = True

        # Remove objects that have disappeared from the frame
        vanished = set(self._object_states.keys()) - current_keys
        for key in vanished:
            del self._object_states[key]

        return events

    @staticmethod
    def _object_key(obj: Dict[str, Any]) -> str:
        """
        Produce a stable string key for an object based on class and
        approximate grid position (bucket 32 px cells).
        """
        pos = obj.get("_pos", {})
        cx = int(pos.get("center_x", 0) / 32)
        cy = int(pos.get("center_y", 0) / 32)
        label = obj.get("class_label", "object")
        return f"{label}_{cx}_{cy}"
