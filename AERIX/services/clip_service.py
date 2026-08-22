"""
Phase 12 — Clip Service

Input: Event ID
↓
Find timestamp
↓
Locate original video
↓
FFmpeg
↓
Extract ±15–30 seconds
↓
Return clip.mp4
"""

import subprocess
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from database.models.event import Event
from database.models.video import Video
from backend.core.config import settings


class ClipService:
    """Service for extracting video clips from events"""
    
    def __init__(self, clip_duration: int = 30, output_dir: Optional[Path] = None):
        """
        Initialize clip service
        
        Args:
            clip_duration: Duration of clip in seconds (default: 30)
            output_dir: Directory to save clips
        """
        self.clip_duration = clip_duration
        self.output_dir = output_dir or (settings.PROJECT_ROOT / "storage" / "clips")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_clip(
        self,
        event_id: str,
        db: Session
    ) -> dict:
        """
        Extract video clip for an event
        
        Args:
            event_id: UUID of the event
            db: Database session
            
        Returns:
            Dictionary with clip information
            
        Raises:
            HTTPException: If event or video not found
        """
        # Validate event ID
        try:
            event_uuid = uuid.UUID(event_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid event ID format")
        
        # Get event from database
        event = db.query(Event).filter(Event.id == event_uuid).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Get associated video
        if not event.video_id:
            raise HTTPException(status_code=404, detail="No video associated with this event")
        
        video = db.query(Video).filter(Video.id == event.video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Check if video file exists
        video_path = Path(video.file_path)
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found on disk")
        
        # Calculate clip timing using frame_number for accuracy
        video_fps = getattr(video, "fps", 30.0) or 30.0
        event_time_seconds = self._timestamp_to_seconds(
            event.timestamp,
            getattr(video, "start_time", None),
            frame_number=event.frame_number,
            video_fps=video_fps,
        )
        
        # Extract ±15 seconds (30 seconds total)
        start_time = max(0, event_time_seconds - 15)
        duration = self.clip_duration
        
        # Generate output filename
        clip_filename = f"clip_{event_id}_{uuid.uuid4().hex[:8]}.mp4"
        clip_path = self.output_dir / clip_filename
        
        # Extract clip using FFmpeg
        success = self._extract_with_ffmpeg(
            video_path=str(video_path),
            output_path=str(clip_path),
            start_time=start_time,
            duration=duration
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to extract clip")
        
        # Generate relative URL for frontend
        clip_url = f"/clips/{clip_filename}"
        
        return {
            "event_id": str(event_id),
            "clip_url": clip_url,
            "clip_path": str(clip_path),
            "duration": duration,
            "event_timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type
        }
    
    def _timestamp_to_seconds(
        self,
        event_timestamp,
        video_start_time,
        frame_number: int | None = None,
        video_fps: float = 30.0,
    ) -> float:
        """
        Convert event timestamp to seconds from video start.

        Resolution priority:
        1. frame_number / video_fps  — most accurate; always available from pipeline
        2. (event_timestamp - video_start_time).total_seconds()  — when both datetimes exist
        3. Falls back to 15 s so clip extraction never hard-crashes

        Args:
            event_timestamp: Event datetime stored in the DB
            video_start_time: Video start datetime (Video.start_time, may be None)
            frame_number: Frame number from Event.frame_number
            video_fps: FPS the video was processed at (default 30)

        Returns:
            Seconds from video start
        """
        # Option 1 — frame-number based (most reliable)
        if frame_number is not None and frame_number > 0:
            return frame_number / max(video_fps, 1.0)

        # Option 2 — datetime delta
        if event_timestamp and video_start_time:
            try:
                delta = (event_timestamp - video_start_time).total_seconds()
                if delta >= 0:
                    return delta
            except Exception:
                pass

        # Option 3 — safe fallback
        return 15.0
    
    def _extract_with_ffmpeg(
        self,
        video_path: str,
        output_path: str,
        start_time: float,
        duration: int
    ) -> bool:
        """
        Extract clip using FFmpeg
        
        Args:
            video_path: Path to source video
            output_path: Path to output clip
            start_time: Start time in seconds
            duration: Duration in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # FFmpeg command to extract clip
            # -ss: start time
            # -i: input file
            # -t: duration
            # -c copy: copy codec (fast, no re-encoding)
            # -y: overwrite output file
            command = [
                "ffmpeg",
                "-ss", str(start_time),
                "-i", video_path,
                "-t", str(duration),
                "-c", "copy",
                "-y",
                output_path
            ]
            
            # Run FFmpeg
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print(f"FFmpeg timeout extracting clip from {video_path}")
            return False
        except FileNotFoundError:
            print("FFmpeg not found. Please install FFmpeg.")
            return False
        except Exception as e:
            print(f"Error extracting clip: {e}")
            return False
