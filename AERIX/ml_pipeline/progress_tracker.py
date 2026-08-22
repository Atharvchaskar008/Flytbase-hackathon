"""
Progress Tracker - Real-time processing status updates

Phase 10 Implementation:
- Tracks processing progress (0-100%)
- Updates database in real-time
- Provides progress messages for frontend display
"""

from sqlalchemy.orm import Session
from database.repository.video_repository import update_progress


class ProgressTracker:
    """Tracks and updates video processing progress"""
    
    def __init__(self, db: Session, video_id: str, total_frames: int = 0):
        """
        Initialize progress tracker
        
        Args:
            db: Database session
            video_id: UUID of video being processed
            total_frames: Total frames to process
        """
        self.db = db
        self.video_id = video_id
        self.total_frames = total_frames
        self.processed_frames = 0
        self.current_step = "initializing"
        self.step_progress = 0  # Progress within current step (0-100)
        
        # Define processing steps with their weight in overall progress
        self.steps = [
            ("loading", 5, "Loading video"),
            ("sampling", 5, "Sampling frames"),
            ("detecting", 30, "Running YOLO detection"),
            ("tracking", 20, "Tracking objects"),
            ("events", 10, "Generating events"),
            ("reid", 15, "Extracting Re-ID embeddings"),
            ("clip", 10, "Extracting CLIP embeddings"),
            ("saving", 5, "Saving to database"),
        ]
        self.current_step_idx = 0
        
        # Initialize progress
        self._update(0, "Initializing pipeline")
    
    def set_total_frames(self, total: int):
        """Set total frames for frame-based progress"""
        self.total_frames = total
        update_progress(
            self.db,
            self.video_id,
            progress=self._calculate_progress(),
            progress_message=self.current_step,
            frames_total=total,
            frames_processed=self.processed_frames
        )
    
    def set_step(self, step_name: str):
        """Set current processing step"""
        for idx, (name, weight, message) in enumerate(self.steps):
            if name == step_name:
                self.current_step_idx = idx
                self.current_step = message
                self.step_progress = 0
                self._update(self._calculate_progress(), message)
                break
    
    def update_frame_progress(self, frames_processed: int):
        """Update progress based on frames processed"""
        self.processed_frames = frames_processed
        
        if self.total_frames > 0:
            # Calculate step progress
            self.step_progress = int((frames_processed / self.total_frames) * 100)
            
            # Update database
            progress = self._calculate_progress()
            message = f"{self.current_step} ({self.step_progress}%)"
            
            update_progress(
                self.db,
                self.video_id,
                progress=progress,
                progress_message=message,
                frames_processed=frames_processed,
                status="processing"
            )
    
    def complete_step(self, step_name: str):
        """Mark a step as complete"""
        for idx, (name, weight, message) in enumerate(self.steps):
            if name == step_name:
                self.current_step_idx = idx
                self.step_progress = 100
                self._update(self._calculate_progress(), f"{message} - Complete")
                break
    
    def complete(self, stats: dict = None):
        """Mark processing as complete"""
        message = "Processing complete"
        if stats:
            message = f"Complete - {stats.get('total_tracks', 0)} tracks, {stats.get('total_events', 0)} events"
        
        update_progress(
            self.db,
            self.video_id,
            progress=100,
            progress_message=message,
            frames_processed=self.total_frames,
            status="processed"
        )
    
    def fail(self, error_message: str):
        """Mark processing as failed"""
        update_progress(
            self.db,
            self.video_id,
            progress=self.step_progress,
            progress_message=f"Failed: {error_message}",
            status="failed"
        )
    
    def _calculate_progress(self) -> int:
        """Calculate overall progress percentage"""
        if not self.steps:
            return 0
        
        # Calculate completed steps progress
        completed_progress = sum(
            weight for idx, (_, weight, _) in enumerate(self.steps)
            if idx < self.current_step_idx
        )
        
        # Add current step progress
        current_weight = self.steps[self.current_step_idx][1] if self.current_step_idx < len(self.steps) else 0
        current_step_contribution = (current_weight * self.step_progress) / 100
        
        total = completed_progress + current_step_contribution
        return int(total)
    
    def _update(self, progress: int, message: str):
        """Update database with current progress"""
        update_progress(
            self.db,
            self.video_id,
            progress=progress,
            progress_message=message,
            frames_processed=self.processed_frames,
            status="processing"
        )
