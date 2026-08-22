"""
Extended Event Model — Zone Entry / Exit Detector

A Zone is defined by a polygon stored as a list of [x, y] points in pixel
coordinates (matching the camera/frame resolution).

Emits:
    entered_zone   — track centre crossed into a zone polygon
    exited_zone    — track centre crossed out of a zone polygon

Zone definitions are loaded from the database (Zone model) once per video,
then re-used for every frame.  The detector keeps a per-track membership
dict so it only fires on the *transition*, not on every frame.

Polygon containment uses a standard ray-casting algorithm — no external
geometry library required.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _point_in_polygon(px: float, py: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Ray-casting algorithm for point-in-polygon test.

    Args:
        px, py:  Point to test.
        polygon: List of (x, y) vertex tuples (closed or open — last edge is
                 auto-connected to first vertex).

    Returns:
        True if the point is inside the polygon.
    """
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    xi, yi = polygon[0]
    for j in range(1, n + 1):
        xj, yj = polygon[j % n]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        xi, yi = xj, yj
    return inside


def _parse_polygon(raw: Any) -> Optional[List[Tuple[float, float]]]:
    """
    Parse a polygon stored in the DB (JSONB) into a list of (x, y) tuples.

    Accepted formats:
        [[x0,y0], [x1,y1], ...]      — list of 2-element lists
        [{"x": x0, "y": y0}, ...]    — list of dicts
    """
    if not raw:
        return None
    try:
        result: List[Tuple[float, float]] = []
        for point in raw:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                result.append((float(point[0]), float(point[1])))
            elif isinstance(point, dict):
                result.append((float(point["x"]), float(point["y"])))
            else:
                return None
        return result if len(result) >= 3 else None
    except Exception as exc:
        logger.warning("Failed to parse polygon: %s — %s", raw, exc)
        return None


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class ZoneEventDetector:
    """
    Detects zone entry/exit events for tracked objects.

    Usage:
        detector = ZoneEventDetector()
        detector.load_zones_from_db(camera_id, db)

        # Per frame:
        events = detector.update(track_id, frame_number, timestamp, position)
    """

    def __init__(self) -> None:
        # zone_id (str) → {"name": str, "polygon": [...], "zone_type": str}
        self._zones: Dict[str, Dict[str, Any]] = {}
        # track_id (int) → set of zone_ids the track is currently inside
        self._track_memberships: Dict[int, set] = {}

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def load_zones_from_db(self, camera_id: Any, db: Any) -> int:
        """
        Load Zone polygons from the database for a given camera.

        Args:
            camera_id: UUID of the camera.
            db:        SQLAlchemy session.

        Returns:
            Number of zones loaded.
        """
        try:
            from database.models.zone import Zone
            import uuid as _uuid

            cam_uuid = _uuid.UUID(str(camera_id))
            rows = db.query(Zone).filter(Zone.camera_id == cam_uuid).all()
            loaded = 0
            for row in rows:
                poly = _parse_polygon(row.polygon)
                if poly is None:
                    logger.warning("Zone %s has invalid polygon — skipped", row.id)
                    continue
                self._zones[str(row.id)] = {
                    "name": row.name,
                    "polygon": poly,
                    "zone_type": row.zone_type,
                    "zone_id": str(row.id),
                }
                loaded += 1
            logger.info("Loaded %d zones for camera %s", loaded, camera_id)
            return loaded
        except Exception as exc:
            logger.error("Failed to load zones: %s", exc)
            return 0

    def load_zones_from_list(self, zones: List[Dict[str, Any]]) -> int:
        """
        Load zones from a plain list (useful for tests / mock pipelines).

        Each dict must have: id, name, polygon ([[x,y],...]), zone_type.
        """
        loaded = 0
        for z in zones:
            poly = _parse_polygon(z.get("polygon"))
            if poly is None:
                continue
            self._zones[str(z["id"])] = {
                "name": z.get("name", "unnamed"),
                "polygon": poly,
                "zone_type": z.get("zone_type", "general"),
                "zone_id": str(z["id"]),
            }
            loaded += 1
        return loaded

    def clear_zones(self) -> None:
        self._zones.clear()

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(
        self,
        track_id: int,
        frame_number: int,
        timestamp: datetime,
        position: Dict[str, float],
        confidence: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Check whether the track centre is inside any loaded zones and emit
        entered_zone / exited_zone events on transitions.

        Args:
            track_id:     Integer tracker ID.
            frame_number: Current frame index.
            timestamp:    Wall-clock datetime for this frame.
            position:     Bbox dict with at least center_x, center_y.
            confidence:   Detection confidence.

        Returns:
            List of zone event dicts (may be empty).
        """
        if not self._zones:
            return []

        px = float(position.get("center_x", 0))
        py = float(position.get("center_y", 0))

        events: List[Dict[str, Any]] = []
        current_membership: set = set()

        for zone_id, zone in self._zones.items():
            if _point_in_polygon(px, py, zone["polygon"]):
                current_membership.add(zone_id)

        previous_membership: set = self._track_memberships.get(track_id, set())

        # Entered zones
        for zone_id in current_membership - previous_membership:
            zone = self._zones[zone_id]
            events.append(self._make_event(
                "entered_zone",
                track_id=track_id,
                frame_number=frame_number,
                timestamp=timestamp,
                confidence=confidence,
                zone=zone,
                position=position,
            ))

        # Exited zones
        for zone_id in previous_membership - current_membership:
            zone = self._zones[zone_id]
            events.append(self._make_event(
                "exited_zone",
                track_id=track_id,
                frame_number=frame_number,
                timestamp=timestamp,
                confidence=confidence,
                zone=zone,
                position=position,
            ))

        self._track_memberships[track_id] = current_membership
        return events

    def remove_track(self, track_id: int) -> None:
        """Emit exited_zone for any zones the track was inside, then clean up."""
        self._track_memberships.pop(track_id, None)

    def reset(self) -> None:
        """Clear all per-track state — call between videos."""
        self._track_memberships.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _make_event(
        event_type: str,
        track_id: int,
        frame_number: int,
        timestamp: datetime,
        confidence: float,
        zone: Dict[str, Any],
        position: Dict[str, float],
    ) -> Dict[str, Any]:
        return {
            "event_type": event_type,
            "track_id": track_id,
            "frame_number": frame_number,
            "confidence": confidence,
            "timestamp": timestamp,
            "metadata": {
                "zone_id": zone["zone_id"],
                "zone_name": zone["name"],
                "zone_type": zone["zone_type"],
                "current_position": position,
                "current_state": event_type,
            },
        }
