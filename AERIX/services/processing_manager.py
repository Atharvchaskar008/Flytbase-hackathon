"""
Phase 14 - Processing Manager ⭐⭐⭐⭐⭐

Every uploaded video should expose its current state:

Uploaded → Queued → Processing → Detecting Objects → 
Tracking → Generating Embeddings → Completed

This makes the backend robust and the frontend can show progress.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from enum import Enum

from database.models.video import Video
from database.repository.video_repository import get_video, update_status

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """Processing stages for video processing"""
    UPLOADED = "uploaded"
    QUEUED = "queued"
    LOADING = "loading"
    SAMPLING = "sampling"
    DETECTING = "detecting"
    TRACKING = "tracking"
    EVENTS = "events"
    REID_EMBEDDINGS = "reid_embeddings"
    CLIP_EMBEDDINGS = "clip_embeddings"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingManager:
    """
    Manages processing state for all videos.
    
    This manager:
    1. Tracks processing stages
    2. Updates progress percentages
    3. Provides status to frontend
    4. Handles error states
    5. Manages queuing
    """
    
    def __init__(self):
        """Initialize processing manager"""
        self.stage_weights = {
            ProcessingStage.UPLOADED: 0,
            ProcessingStage.QUEUED: 5,
            ProcessingStage.LOADING: 10,
            ProcessingStage.SAMPLING: 15,
            ProcessingStage.DETECTING: 40,  # Most time-consuming
            ProcessingStage.TRACKING: 65,
            ProcessingStage.EVENTS: 75,
            ProcessingStage.REID_EMBEDDINGS: 85,
            ProcessingStage.CLIP_EMBEDDINGS: 95,
            ProcessingStage.SAVING: 98,
            ProcessingStage.COMPLETED: 100,
            ProcessingStage.FAILED: 0
        }
        
    def start_processing(self, video_id: str, db: Session) -> None:
        """
        Mark video as starting to process
        
        Args:
            video_id: UUID of video
            db: Database session
        """
        logger.info(f"🚀 Starting processing for video: {video_id}")
        
        self._update_video_status(
            video_id, db,
            status="processing",
            progress=5,
            progress_message="Starting video processing...",
            stage=ProcessingStage.QUEUED.value
        )
    
    def set_stage(
        self, 
        video_id: str, 
        db: Session, 
        stage: str, 
        message: str
    ) -> None:
        """
        Update processing stage
        
        Args:
            video_id: UUID of video
            db: Database session
            stage: Current processing stage
            message: Human-readable progress message
        """
        try:
            stage_enum = ProcessingStage(stage)
        except ValueError:
            logger.warning(f"Unknown processing stage: {stage}")
            return
        
        progress = self.stage_weights[stage_enum]
        
        logger.info(f"📊 Video {video_id}: {stage} - {message} ({progress}%)")
        
        self._update_video_status(
            video_id, db,
            progress=progress,
            progress_message=message,
            stage=stage
        )
    
    def set_total_frames(self, video_id: str, db: Session, total_frames: int) -> None:
        """
        Set total frames for progress calculation
        
        Args:
            video_id: UUID of video
            db: Database session
            total_frames: Total number of frames in video
        """
        video = get_video(db, video_id)
        if video:
            video.frames_total = total_frames
            db.commit()
            logger.info(f"📹 Video {video_id}: Total frames set to {total_frames}")
    
    def update_progress(
        self, 
        video_id: str, 
        db: Session, 
        frames_processed: int
    ) -> None:
        """
        Update processing progress based on frames processed
        
        Args:
            video_id: UUID of video
            db: Database session
            frames_processed: Number of frames processed so far
        """
        video = get_video(db, video_id)
        if not video or not video.frames_total:
            return
        
        # Calculate frame progress (within current stage)
        frame_progress = (frames_processed / video.frames_total) * 100
        
        # Update frames processed
        video.frames_processed = frames_processed
        
        # Get current stage progress and add frame progress
        current_stage = ProcessingStage(video.status)
        base_progress = self.stage_weights[current_stage]
        
        # Add frame progress within the stage range
        if current_stage == ProcessingStage.DETECTING:
            # Detection stage is 40-65%, so frame progress fills that range
            stage_range = 25  # 65 - 40
            detailed_progress = base_progress + (frame_progress * stage_range / 100)
        else:
            detailed_progress = base_progress
        
        detailed_progress = min(detailed_progress, 98)  # Cap at 98% until completion
        
        self._update_video_status(
            video_id, db,
            progress=int(detailed_progress),
            progress_message=f"Processing frames... ({frames_processed}/{video.frames_total})"
        )
    
    def complete_processing(
        self, 
        video_id: str, 
        db: Session, 
        stats: Dict[str, Any]
    ) -> None:
        """
        Mark video processing as completed
        
        Args:
            video_id: UUID of video
            db: Database session
            stats: Processing statistics
        """
        logger.info(f"✅ Completed processing for video: {video_id}")
        
        completion_message = (
            f"Complete - {stats.get('total_tracks', 0)} tracks, "
            f"{stats.get('total_events', 0)} events"
        )
        
        self._update_video_status(
            video_id, db,
            status="completed",
            progress=100,
            progress_message=completion_message,
            stage=ProcessingStage.COMPLETED.value
        )
        
        # Update video metadata
        video = get_video(db, video_id)
        if video:
            video.end_time = datetime.now()
            if video.start_time:
                video.duration_seconds = int(
                    (video.end_time - video.start_time).total_seconds()
                )
            db.commit()
    
    def fail_processing(
        self, 
        video_id: str, 
        db: Session, 
        error_message: str
    ) -> None:
        """
        Mark video processing as failed
        
        Args:
            video_id: UUID of video
            db: Database session
            error_message: Error description
        """
        logger.error(f"❌ Failed processing for video: {video_id} - {error_message}")
        
        self._update_video_status(
            video_id, db,
            status="failed",
            progress=0,
            progress_message=f"Failed: {error_message}",
            stage=ProcessingStage.FAILED.value
        )
    
    def get_status(self, video_id: str, db: Session) -> Dict[str, Any]:
        """
        Get current processing status
        
        Args:
            video_id: UUID of video
            db: Database session
            
        Returns:
            Current status information
        """
        video = get_video(db, video_id)
        if not video:
            return {
                'status': 'not_found',
                'error': 'Video not found'
            }
        
        # Calculate ETA if processing
        eta_seconds = None
        if video.status == "processing" and video.frames_processed and video.frames_total:
            if video.frames_processed > 0:
                processing_time = (datetime.now() - video.start_time).total_seconds()
                frames_per_second = video.frames_processed / processing_time
                remaining_frames = video.frames_total - video.frames_processed
                eta_seconds = int(remaining_frames / frames_per_second) if frames_per_second > 0 else None
        
        return {
            'video_id': str(video.id),
            'filename': video.filename,
            'status': video.status,
            'progress': video.progress,
            'progress_message': video.progress_message,
            'frames_total': video.frames_total,
            'frames_processed': video.frames_processed,
            'created_at': video.created_at.isoformat() if video.created_at else None,
            'start_time': video.start_time.isoformat() if video.start_time else None,
            'end_time': video.end_time.isoformat() if video.end_time else None,
            'duration_seconds': video.duration_seconds,
            'eta_seconds': eta_seconds
        }
    
    def get_all_status(self, db: Session) -> Dict[str, Any]:
        """
        Get status of all videos
        
        Args:
            db: Database session
            
        Returns:
            Status of all videos grouped by status
        """
        from sqlalchemy import func
        
        # Get status counts
        status_counts = (
            db.query(Video.status, func.count(Video.id))
            .group_by(Video.status)
            .all()
        )
        
        # Get currently processing videos
        processing_videos = (
            db.query(Video)
            .filter(Video.status == "processing")
            .order_by(Video.start_time.desc())
            .limit(10)
            .all()
        )
        
        # Get recent completions
        recent_completed = (
            db.query(Video)
            .filter(Video.status == "completed")
            .order_by(Video.end_time.desc())
            .limit(5)
            .all()
        )
        
        return {
            'status_counts': {status: count for status, count in status_counts},
            'currently_processing': [
                {
                    'video_id': str(v.id),
                    'filename': v.filename,
                    'progress': v.progress,
                    'progress_message': v.progress_message,
                    'start_time': v.start_time.isoformat() if v.start_time else None
                }
                for v in processing_videos
            ],
            'recent_completed': [
                {
                    'video_id': str(v.id),
                    'filename': v.filename,
                    'end_time': v.end_time.isoformat() if v.end_time else None,
                    'duration_seconds': v.duration_seconds
                }
                for v in recent_completed
            ],
            'total_videos': sum(count for _, count in status_counts)
        }
    
    def queue_video(self, video_id: str, db: Session) -> None:
        """
        Add video to processing queue
        
        Args:
            video_id: UUID of video
            db: Database session
        """
        logger.info(f"📋 Queuing video for processing: {video_id}")
        
        self._update_video_status(
            video_id, db,
            status="queued",
            progress=0,
            progress_message="Queued for processing",
            stage=ProcessingStage.QUEUED.value
        )
        
        # Set start time when queued
        video = get_video(db, video_id)
        if video:
            video.start_time = datetime.now()
            db.commit()
    
    def _update_video_status(
        self, 
        video_id: str, 
        db: Session, 
        status: Optional[str] = None,
        progress: Optional[int] = None,
        progress_message: Optional[str] = None,
        stage: Optional[str] = None
    ) -> None:
        """
        Update video status in database
        
        Args:
            video_id: UUID of video
            db: Database session
            status: New status (optional)
            progress: Progress percentage (optional)
            progress_message: Progress message (optional)
            stage: Processing stage (optional)
        """
        video = get_video(db, video_id)
        if not video:
            logger.error(f"Video not found for status update: {video_id}")
            return
        
        if status is not None:
            video.status = status
        if progress is not None:
            video.progress = progress
        if progress_message is not None:
            video.progress_message = progress_message
        
        video.updated_at = datetime.now()
        
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Failed to update video status: {e}")
            db.rollback()
    
    def get_queue_status(self, db: Session) -> Dict[str, Any]:
        """
        Get processing queue status
        
        Args:
            db: Database session
            
        Returns:
            Queue information
        """
        queued_videos = (
            db.query(Video)
            .filter(Video.status == "queued")
            .order_by(Video.created_at.asc())
            .all()
        )
        
        processing_videos = (
            db.query(Video)
            .filter(Video.status == "processing")
            .all()
        )
        
        return {
            'queue_length': len(queued_videos),
            'currently_processing': len(processing_videos),
            'queued_videos': [
                {
                    'video_id': str(v.id),
                    'filename': v.filename,
                    'queued_at': v.created_at.isoformat(),
                    'position': i + 1
                }
                for i, v in enumerate(queued_videos)
            ]
        }