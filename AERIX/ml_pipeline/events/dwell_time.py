"""
Extended Event Model — Loitering / Dwell-Time Detector

Tracks how long each object has been stationary (speed below threshold).
Emits:
    loitering          — person has been still for >= loiter_seconds
    standing_long_time — person has been in scene for >= long_stay_seconds (any motion)

Called once per frame from EventIntelligenceService after the tracker update.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class DwellTimeDetector:
    """
    Per-track dwell-time / loitering detector.

    State is kept in-process across frames; reset on track loss.

    Args:
        loiter_seconds:    Seconds a track must be *stationary* before emitting
                           a ``loitering`` event (default 30 s).
        long_stay_seconds: Seconds a track must be *in the scene at all* before
                           emitting a ``standing_long_time`` event (default 120 s).
        video_fps:         FPS used to convert frame numbers to wall-clock seconds.
        speed_stop_threshold: Maximum pixel-per-frame speed still considered
                              "stationary" (matches EventIntelligenceService).
    """

    def __init__(
        self,
        loiter_seconds: float = 30.0,
        long_stay_seconds: float = 120.0,
        video_fps: float = 30.0,
        speed_stop_threshold: float = 1.0,
    ) -> None:
        self.loiter_seconds = loiter_seconds
        self.long_stay_seconds = long_stay_seconds
        self.video_fps = video_fps
        self.speed_stop_threshold = speed_stop_threshold

        # track_id (int) → state dict
        self._states: Dict[int, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        track_id: int,
        frame_number: int,
        timestamp: datetime,
        speed: float,
        position: Dict[str, float],
        confidence: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Update dwell state for one track and return any new events.

        Args:
            track_id:    Integer tracker ID.
            frame_number: Current frame index.
            timestamp:   Wall-clock datetime for this frame.
            speed:       Pixel-per-frame speed from EventIntelligenceService.
            position:    Bbox dict with center_x, center_y (and x, y, w, h).
            confidence:  Detection confidence.

        Returns:
            List of event dicts (may be empty).
        """
        events: List[Dict[str, Any]] = []
        state = self._states.get(track_id)

        if state is None:
            # First time we see this track
            self._states[track_id] = {
                "first_frame": frame_number,
                "first_ts": timestamp,
                "stationary_since_frame": frame_number if speed <= self.speed_stop_threshold else None,
                "stationary_since_ts": timestamp if speed <= self.speed_stop_threshold else None,
                "loitering_emitted": False,
                "long_stay_emitted": False,
                "last_position": position,
            }
            return events

        # ---- Total scene presence ----------------------------------------
        scene_seconds = (timestamp - state["first_ts"]).total_seconds()
        if not state["long_stay_emitted"] and scene_seconds >= self.long_stay_seconds:
            events.append(self._make_event(
                event_type="standing_long_time",
                track_id=track_id,
                frame_number=frame_number,
                timestamp=timestamp,
                confidence=confidence,
                extra={
                    "duration_seconds": round(scene_seconds, 1),
                    "current_position": position,
                    "speed": speed,
                },
            ))
            state["long_stay_emitted"] = True

        # ---- Stationary streak -------------------------------------------
        is_stationary = speed <= self.speed_stop_threshold
        if is_stationary:
            if state["stationary_since_frame"] is None:
                # Just became stationary
                state["stationary_since_frame"] = frame_number
                state["stationary_since_ts"] = timestamp
            else:
                # Continuing to be stationary
                stationary_seconds = (timestamp - state["stationary_since_ts"]).total_seconds()
                if not state["loitering_emitted"] and stationary_seconds >= self.loiter_seconds:
                    events.append(self._make_event(
                        event_type="loitering",
                        track_id=track_id,
                        frame_number=frame_number,
                        timestamp=timestamp,
                        confidence=confidence,
                        extra={
                            "stationary_seconds": round(stationary_seconds, 1),
                            "current_position": position,
                            "speed": speed,
                        },
                    ))
                    state["loitering_emitted"] = True
        else:
            # Moving again — reset stationary streak and allow future loitering events
            state["stationary_since_frame"] = None
            state["stationary_since_ts"] = None
            state["loitering_emitted"] = False

        state["last_position"] = position
        return events

    def remove_track(self, track_id: int) -> None:
        """Called when a track is lost so we free its state."""
        self._states.pop(track_id, None)

    def reset(self) -> None:
        """Clear all state — call between videos."""
        self._states.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_event(
        event_type: str,
        track_id: int,
        frame_number: int,
        timestamp: datetime,
        confidence: float,
        extra: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "event_type": event_type,
            "track_id": track_id,
            "frame_number": frame_number,
            "confidence": confidence,
            "timestamp": timestamp,
            "metadata": {
                "current_state": event_type,
                **extra,
            },
        }
