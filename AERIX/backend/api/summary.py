"""
Phase 17 — Video Summary API

GET  /videos/{video_id}/summary
    Returns a full narrative summary of everything that happened in a video:
    - Human-readable prose paragraph (built from VLM descriptions + event templates)
    - Per-track summaries (first/last seen, duration, key events)
    - Statistical breakdown (event type counts, longest track, etc.)
    - Highlight sentences (loitering, falls, abandoned objects, long stays)

POST /videos/{video_id}/summary/regenerate
    Clears cached summaries and re-runs the engine (useful after re-processing).
"""

from __future__ import annotations

import uuid
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.session import get_db
from services.video_summary_engine import VideoSummaryEngine, VideoSummaryResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["summary"])

# Single shared engine instance (stateless — safe to reuse)
_engine = VideoSummaryEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_video_id(video_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid video ID: {video_id!r}")


def _summary_to_dict(result: VideoSummaryResult) -> Dict[str, Any]:
    return {
        "video_id": result.video_id,
        "generated_at": result.generated_at,
        "total_tracks": result.total_tracks,
        "total_events": result.total_events,
        "duration_seconds": result.duration_seconds,
        "narrative": result.narrative,
        "track_summaries": result.track_summaries,
        "highlights": result.highlights,
        "statistics": result.statistics,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{video_id}/summary")
def get_video_summary(
    video_id: str,
    include_track_summaries: bool = Query(True, description="Include per-track detail"),
    include_statistics: bool = Query(True, description="Include event-type statistics"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Generate and return a narrative summary for a processed video.

    The summary is built on-the-fly from the events, tracks, and descriptions
    already stored in the database — no re-processing of video frames needed.

    Example narrative:

        Video Summary

        A man wearing a red cap entered the camera view.
        They walked toward the far side of the frame.
        They stopped moving at 10:34.
        They were present for approximately 3 minutes 22 seconds.

    Args:
        video_id: UUID of the video to summarise.
        include_track_summaries: Whether to include per-track breakdown.
        include_statistics: Whether to include event-type statistics.

    Returns:
        JSON object with narrative, track summaries, highlights, and statistics.
    """
    vid = _validate_video_id(video_id)

    # Verify the video exists
    from database.models.video import Video
    video = db.query(Video).filter(Video.id == vid).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    logger.info("Generating summary for video %s", video_id)

    try:
        result = _engine.summarize(vid, db)
    except Exception as exc:
        logger.error("Summary generation failed for video %s: %s", video_id, exc)
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {exc}")

    response = _summary_to_dict(result)

    if not include_track_summaries:
        response.pop("track_summaries", None)
    if not include_statistics:
        response.pop("statistics", None)

    return response


@router.get("/{video_id}/summary/narrative")
def get_video_narrative(
    video_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return only the narrative prose for a video — lightweight endpoint
    suited for display in a UI card or tooltip.

    Returns:
        { "video_id": "...", "narrative": "..." }
    """
    vid = _validate_video_id(video_id)

    from database.models.video import Video
    video = db.query(Video).filter(Video.id == vid).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    try:
        result = _engine.summarize(vid, db)
    except Exception as exc:
        logger.error("Narrative generation failed for video %s: %s", video_id, exc)
        raise HTTPException(status_code=500, detail=f"Narrative generation failed: {exc}")

    return {
        "video_id": result.video_id,
        "narrative": result.narrative,
        "generated_at": result.generated_at,
        "total_tracks": result.total_tracks,
        "highlights": result.highlights,
    }


@router.get("/{video_id}/summary/highlights")
def get_video_highlights(
    video_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return only the highlight sentences for a video (loitering, falls,
    abandoned objects, long stays) — useful for alert / notification UIs.

    Returns:
        { "video_id": "...", "highlights": [...] }
    """
    vid = _validate_video_id(video_id)

    from database.models.video import Video
    video = db.query(Video).filter(Video.id == vid).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    try:
        result = _engine.summarize(vid, db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Highlights generation failed: {exc}")

    return {
        "video_id": result.video_id,
        "highlights": result.highlights,
        "generated_at": result.generated_at,
    }
