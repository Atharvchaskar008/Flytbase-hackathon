"""
Phase 17 — Video Summary Engine

Input:
    Events  +  Descriptions  +  Tracks
Output:
    Human-readable narrative summary

Example output:
    Video Summary

    One male wearing a red cap entered the mall.
    He walked toward the electronics section.
    He stopped for approximately one minute.
    He picked up a laptop box.
    He returned the laptop to the shelf.
    He exited through the main entrance.

The engine groups raw events into meaningful episodes per track, gathers the
VLM descriptions attached to each keyframe, then builds a narrative paragraph
using a simple template-chain approach.  When a real LLM is wired in (see
_llm_narrate()), the templates are replaced by actual prose generation.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TrackEpisode:
    """A single track's complete activity in one video."""
    track_id: str
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    descriptions: List[str] = field(default_factory=list)
    objects_seen: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.first_seen and self.last_seen:
            return (self.last_seen - self.first_seen).total_seconds()
        return 0.0

    @property
    def event_types(self) -> List[str]:
        return [e.get("event_type", "") for e in self.events]


@dataclass
class VideoSummaryResult:
    video_id: str
    generated_at: str
    total_tracks: int
    total_events: int
    duration_seconds: float
    narrative: str                       # full human-readable text
    track_summaries: List[Dict[str, Any]]
    highlights: List[str]
    statistics: Dict[str, Any]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class VideoSummaryEngine:
    """
    Builds a human-readable narrative summary for a processed video.

    Usage:
        engine = VideoSummaryEngine()
        result = engine.summarize(video_id, db)
        print(result.narrative)
    """

    # Event types that are meaningful enough to mention in a sentence
    _NARRATIVE_EVENTS = {
        "person_entered_scene",
        "person_exited_scene",
        "stopped_moving",
        "running",
        "loitering",
        "direction_changed",
        "object_picked",
        "person_near_object",
        "entered_zone",
        "exited_zone",
        "object_abandoned",
        "fall_detected",
        "crowd_formed",
        "person_disappeared",
    }

    def summarize(self, video_id: str | uuid.UUID, db: Session) -> VideoSummaryResult:
        """
        Generate a complete narrative summary for a video.

        Args:
            video_id: UUID of the video to summarise
            db: SQLAlchemy session

        Returns:
            VideoSummaryResult with narrative text and structured data
        """
        from database.models.event import Event
        from database.models.track import Track
        from database.models.description import Description
        from database.models.video import Video

        vid = uuid.UUID(str(video_id)) if not isinstance(video_id, uuid.UUID) else video_id

        # Load video metadata
        video = db.query(Video).filter(Video.id == vid).first()
        video_start: Optional[datetime] = getattr(video, "start_time", None) if video else None

        # Load all events for this video ordered by time
        events = (
            db.query(Event)
            .filter(Event.video_id == vid)
            .order_by(Event.timestamp.asc())
            .all()
        )

        # Load all tracks for this video
        tracks = (
            db.query(Track)
            .filter(Track.video_id == vid)
            .order_by(Track.first_seen.asc())
            .all()
        )

        # Load all descriptions for this video
        descriptions = (
            db.query(Description)
            .filter(Description.video_id == vid)
            .order_by(Description.timestamp.asc())
            .all()
        )

        if not events and not tracks:
            return VideoSummaryResult(
                video_id=str(vid),
                generated_at=datetime.now().isoformat(),
                total_tracks=0,
                total_events=0,
                duration_seconds=0.0,
                narrative="No activity was recorded in this video.",
                track_summaries=[],
                highlights=[],
                statistics={},
            )

        # Build per-track episodes
        episodes = self._build_episodes(events, descriptions, tracks)

        # Generate narrative
        narrative = self._build_narrative(episodes, video_start)

        # Track summaries
        track_summaries = [self._summarize_episode(ep) for ep in episodes]

        # Statistics
        stats = self._compute_statistics(events, tracks, episodes)

        # Highlights (most significant single-sentence observations)
        highlights = self._extract_highlights(episodes)

        # Overall video duration from first/last event timestamp
        duration = 0.0
        if events:
            duration = (events[-1].timestamp - events[0].timestamp).total_seconds()

        return VideoSummaryResult(
            video_id=str(vid),
            generated_at=datetime.now().isoformat(),
            total_tracks=len(tracks),
            total_events=len(events),
            duration_seconds=duration,
            narrative=narrative,
            track_summaries=track_summaries,
            highlights=highlights,
            statistics=stats,
        )

    # ------------------------------------------------------------------
    # Episode building
    # ------------------------------------------------------------------

    def _build_episodes(
        self,
        events,
        descriptions,
        tracks,
    ) -> List[TrackEpisode]:
        """Group events and descriptions by track into TrackEpisode objects."""
        episode_map: Dict[str, TrackEpisode] = {}

        # Index descriptions by track_id
        desc_by_track: Dict[str, List[str]] = defaultdict(list)
        objects_by_track: Dict[str, List[str]] = defaultdict(list)
        for d in descriptions:
            key = str(d.track_id) if d.track_id else "_unknown"
            desc_by_track[key].append(d.description)
            if d.objects:
                objects_by_track[key].extend(d.objects)

        # Seed episodes from tracks (gives us first/last seen)
        for t in tracks:
            key = str(t.id)
            episode_map[key] = TrackEpisode(
                track_id=key,
                first_seen=t.first_seen,
                last_seen=t.last_seen,
                descriptions=desc_by_track.get(key, []),
                objects_seen=list(set(objects_by_track.get(key, []))),
            )

        # Add events to matching episodes
        for ev in events:
            key = str(ev.track_id) if ev.track_id else "_unknown"
            if key not in episode_map:
                episode_map[key] = TrackEpisode(track_id=key)
            ep = episode_map[key]
            if ep.first_seen is None or ev.timestamp < ep.first_seen:
                ep.first_seen = ev.timestamp
            if ep.last_seen is None or ev.timestamp > ep.last_seen:
                ep.last_seen = ev.timestamp
            ep.events.append({
                "event_type": ev.event_type,
                "timestamp": ev.timestamp,
                "frame_number": ev.frame_number,
                "metadata": ev.event_metadata or {},
            })

        # Sort episodes by first_seen
        return sorted(
            episode_map.values(),
            key=lambda ep: ep.first_seen or datetime.min,
        )

    # ------------------------------------------------------------------
    # Narrative generation
    # ------------------------------------------------------------------

    def _build_narrative(
        self,
        episodes: List[TrackEpisode],
        video_start: Optional[datetime],
    ) -> str:
        """Build the full narrative string from all episodes."""
        if not episodes:
            return "No activity was detected in this video."

        lines: List[str] = ["Video Summary", ""]

        for i, ep in enumerate(episodes):
            sentences = self._episode_to_sentences(ep, i + 1, video_start)
            lines.extend(sentences)
            if len(episodes) > 1:
                lines.append("")  # blank line between tracks

        # Try LLM refinement (no-op if not configured)
        raw = "\n".join(lines).strip()
        return self._llm_narrate(raw, episodes)

    def _episode_to_sentences(
        self,
        ep: TrackEpisode,
        track_index: int,
        video_start: Optional[datetime],
    ) -> List[str]:
        """Convert one TrackEpisode into a list of English sentences."""
        sentences: List[str] = []

        pronoun = "A person"
        he = "They"

        # If we have VLM descriptions, extract appearance from the first one
        appearance = ""
        if ep.descriptions:
            first_desc = ep.descriptions[0].strip().rstrip(".")
            # Use the first description sentence as the introduction
            sentences.append(f"{first_desc}.")
            pronoun = he
        else:
            label = f"Person {track_index}"
            sentences.append(f"{pronoun} ({label}) entered the scene.")
            pronoun = he

        # Walk significant events in order
        seen_event_types: set[str] = set()
        for ev in ep.events:
            et = ev.get("event_type", "")
            if et not in self._NARRATIVE_EVENTS:
                continue
            if et == "person_entered_scene":
                continue  # already covered by the intro sentence
            if et in seen_event_types and et not in {
                "direction_changed", "entered_zone", "exited_zone"
            }:
                continue  # don't repeat the same event type

            sentence = self._event_to_sentence(et, ev, pronoun, ep, video_start)
            if sentence:
                sentences.append(sentence)
                seen_event_types.add(et)

        # Duration sentence
        if ep.duration_seconds >= 30:
            dur = self._fmt_duration(ep.duration_seconds)
            sentences.append(f"{he} was present for approximately {dur}.")

        # Picked-up objects
        if ep.objects_seen:
            obj_str = ", ".join(ep.objects_seen[:3])
            sentences.append(f"{he} was seen with: {obj_str}.")

        return sentences

    def _event_to_sentence(
        self,
        event_type: str,
        ev: Dict[str, Any],
        pronoun: str,
        ep: TrackEpisode,
        video_start: Optional[datetime],
    ) -> Optional[str]:
        """Convert a single event into a sentence, or None to skip it."""
        ts = ev.get("timestamp")
        time_phrase = (
            f" at {ts.strftime('%H:%M')}" if isinstance(ts, datetime) else ""
        )

        templates: Dict[str, str] = {
            "stopped_moving":       f"{pronoun} stopped moving{time_phrase}.",
            "running":              f"{pronoun} began running{time_phrase}.",
            "loitering":            f"{pronoun} remained stationary for an extended period{time_phrase}.",
            "direction_changed":    f"{pronoun} changed direction{time_phrase}.",
            "object_picked":        f"{pronoun} picked up an object{time_phrase}.",
            "person_near_object":   f"{pronoun} approached an object of interest{time_phrase}.",
            "entered_zone":         f"{pronoun} entered a monitored zone{time_phrase}.",
            "exited_zone":          f"{pronoun} left the monitored zone{time_phrase}.",
            "object_abandoned":     f"An object was left unattended{time_phrase}.",
            "fall_detected":        f"{pronoun} appears to have fallen{time_phrase}.",
            "crowd_formed":         f"A group of people gathered in the area{time_phrase}.",
            "person_disappeared":   f"{pronoun} disappeared from view{time_phrase}.",
            "person_exited_scene":  f"{pronoun} exited the camera view{time_phrase}.",
        }
        return templates.get(event_type)

    # ------------------------------------------------------------------
    # LLM refinement hook  (no-op unless real LLM is configured)
    # ------------------------------------------------------------------

    def _llm_narrate(self, raw_text: str, episodes: List[TrackEpisode]) -> str:
        """
        Optional: pass the raw narrative through an LLM for fluency refinement.
        Returns raw_text unchanged when no LLM is configured.

        To enable: replace the stub below with an actual LLM call, e.g.
            response = openai_client.chat.completions.create(...)
            return response.choices[0].message.content
        """
        return raw_text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _summarize_episode(self, ep: TrackEpisode) -> Dict[str, Any]:
        return {
            "track_id": ep.track_id,
            "first_seen": ep.first_seen.isoformat() if ep.first_seen else None,
            "last_seen": ep.last_seen.isoformat() if ep.last_seen else None,
            "duration_seconds": round(ep.duration_seconds, 1),
            "duration_human": self._fmt_duration(ep.duration_seconds),
            "event_count": len(ep.events),
            "event_types": list(set(ep.event_types)),
            "description_count": len(ep.descriptions),
            "objects_seen": ep.objects_seen,
            "first_description": ep.descriptions[0] if ep.descriptions else None,
        }

    def _compute_statistics(self, events, tracks, episodes: List[TrackEpisode]) -> Dict[str, Any]:
        event_type_counts: Dict[str, int] = defaultdict(int)
        for ev in events:
            event_type_counts[ev.event_type] += 1

        durations = [ep.duration_seconds for ep in episodes if ep.duration_seconds > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        max_duration = max(durations, default=0.0)

        return {
            "total_tracks": len(tracks),
            "total_events": len(events),
            "event_type_breakdown": dict(event_type_counts),
            "average_track_duration_seconds": round(avg_duration, 1),
            "longest_track_duration_seconds": round(max_duration, 1),
            "tracks_with_descriptions": sum(1 for ep in episodes if ep.descriptions),
        }

    def _extract_highlights(self, episodes: List[TrackEpisode]) -> List[str]:
        highlights: List[str] = []
        for ep in episodes:
            et_set = set(ep.event_types)
            if "loitering" in et_set:
                highlights.append(f"Track {ep.track_id[:8]}: person loitered for {self._fmt_duration(ep.duration_seconds)}.")
            if "running" in et_set:
                highlights.append(f"Track {ep.track_id[:8]}: person was running.")
            if "fall_detected" in et_set:
                highlights.append(f"Track {ep.track_id[:8]}: possible fall detected.")
            if "object_abandoned" in et_set:
                highlights.append(f"Track {ep.track_id[:8]}: object may have been abandoned.")
            if "object_picked" in et_set:
                highlights.append(f"Track {ep.track_id[:8]}: person picked up an object.")
            if ep.duration_seconds > 300:
                highlights.append(f"Track {ep.track_id[:8]}: person present for over 5 minutes.")
        return highlights[:10]

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m} minute{'s' if m != 1 else ''} {s}s" if s else f"{m} minute{'s' if m != 1 else ''}"
        else:
            h, rem = divmod(int(seconds), 3600)
            m = rem // 60
            return f"{h} hour{'s' if h != 1 else ''} {m} min" if m else f"{h} hour{'s' if h != 1 else ''}"
