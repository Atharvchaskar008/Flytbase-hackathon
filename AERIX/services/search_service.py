"""
Phase 16/18 — Search Service

Real database-backed search over Description, Event, and Track tables.
Used by SearchOrchestrator to execute text, event, and track searches.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.description import Description
from database.models.event import Event
from database.models.track import Track
from database.repository.description_repository import search_descriptions

logger = logging.getLogger(__name__)


class SearchService:
    """Database-backed search service."""

    # ------------------------------------------------------------------
    # Text / description search  (Phase 16)
    # ------------------------------------------------------------------

    def text_search(
        self,
        query: str,
        db: Session,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search description table using ILIKE for keyword matches.

        Returns a list of result dicts with all fields needed by
        SearchOrchestrator._format_search_result().
        """
        if not query or not query.strip():
            return []

        rows: List[Description] = search_descriptions(db, query.strip(), max_results)
        results = []
        for row in rows:
            results.append({
                "result_type": "text_match",
                "description_id": str(row.id),
                "track_id": str(row.track_id) if row.track_id else None,
                "keyframe_id": str(row.keyframe_id) if row.keyframe_id else None,
                "video_id": str(row.video_id) if row.video_id else None,
                "frame_number": row.frame_number,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "description": row.description,
                "objects": row.objects or [],
                "confidence": float(row.confidence or 0.0),
                "source": "description_db",
            })

        logger.debug("text_search('%s') → %d results", query, len(results))
        return results

    def image_search_by_description(
        self,
        description: str,
        db: Session,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Alias — delegates to text_search."""
        return self.text_search(description, db, max_results)

    def hybrid_search(
        self,
        query: str,
        db: Session,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Combines text search on descriptions with an event-type keyword search.
        Deduplicates by track_id, keeping the highest-confidence entry.
        """
        text_results = self.text_search(query, db, max_results)

        # Also search event_type column for matching keywords
        event_results = self._event_keyword_search(query, db, max_results)

        # Merge, deduplicate by (track_id, frame_number)
        seen: set[tuple] = set()
        merged: List[Dict[str, Any]] = []
        for r in text_results + event_results:
            key = (r.get("track_id"), r.get("frame_number"))
            if key not in seen:
                seen.add(key)
                merged.append(r)

        merged.sort(key=lambda r: r.get("confidence", 0.0), reverse=True)
        return merged[:max_results]

    def _event_keyword_search(
        self,
        query: str,
        db: Session,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search events whose event_type contains a keyword from the query."""
        keywords = [w.lower().strip() for w in query.split() if len(w) > 2]
        if not keywords:
            return []

        rows: List[Event] = (
            db.query(Event)
            .filter(Event.event_type.ilike(f"%{keywords[0]}%"))
            .order_by(Event.timestamp.desc())
            .limit(max_results)
            .all()
        )
        return [
            {
                "result_type": "event_match",
                "event_id": str(row.id),
                "track_id": str(row.track_id) if row.track_id else None,
                "video_id": str(row.video_id) if row.video_id else None,
                "frame_number": row.frame_number,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "description": row.event_type.replace("_", " ").title(),
                "objects": [],
                "confidence": float(row.score or 0.7),
                "source": "event_db",
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Track / Re-ID similarity search  (Phase 18)
    # ------------------------------------------------------------------

    def find_similar_tracks(
        self,
        track_id: str,
        db: Session,
    ) -> List[Dict[str, Any]]:
        """
        Return tracks that share the same reid_global_id as the given track,
        or tracks whose class_label matches (fallback when no Re-ID is present).
        """
        try:
            tid = uuid.UUID(track_id)
        except ValueError:
            logger.warning("find_similar_tracks: invalid track_id %s", track_id)
            return []

        source_track: Optional[Track] = db.query(Track).filter(Track.id == tid).first()
        if not source_track:
            return []

        # Use reid_global_id if available
        if getattr(source_track, "reid_global_id", None):
            rows: List[Track] = (
                db.query(Track)
                .filter(
                    Track.reid_global_id == source_track.reid_global_id,
                    Track.id != tid,
                )
                .limit(20)
                .all()
            )
        else:
            # Fallback: same class_label
            rows = (
                db.query(Track)
                .filter(
                    Track.class_label == source_track.class_label,
                    Track.id != tid,
                )
                .limit(20)
                .all()
            )

        return [
            {
                "track_id": str(r.id),
                "class_label": r.class_label,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
                "current_state": r.current_state,
                "similarity": 1.0 if getattr(r, "reid_global_id", None) else 0.7,
                "source": "reid_match" if getattr(r, "reid_global_id", None) else "class_match",
            }
            for r in rows
        ]
