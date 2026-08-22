"""
Phase 13 - Pipeline Orchestrator ⭐⭐⭐⭐⭐

This is the SINGLE entry point for all video processing.
One function: process_video(video_id)

The orchestrator connects the entire backend into one cohesive processing pipeline:

Upload Video → Video Loader → Frame Sampler → YOLO Detection → 
Tracker → Event Generator → Embedding Generator → Store Everything
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from pathlib import Path
import traceback

from ml_pipeline.ingestion.video_loader import VideoLoader
from ml_pipeline.ingestion.frame_sampler import FrameSampler
from ml_pipeline.detection.yolo_detector import YOLODetector
from ml_pipeline.tracking.tracker import Tracker
from services.event_intelligence_service import EventIntelligenceService
from ml_pipeline.reid.person_reid import PersonReID
from ml_pipeline.search.clip_search import CLIPSearch

from services.processing_manager import ProcessingManager
from services.validation_service import ValidationService
from database.repository.video_repository import get_video
from database.models.video import Video

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    The single entry point for all video processing.
    
    This orchestrator:
    1. Validates input
    2. Manages processing state
    3. Coordinates all ML components
    4. Handles errors gracefully
    5. Ensures data consistency
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the pipeline orchestrator"""
        self.config = config or self._default_config()
        self.processing_manager = ProcessingManager()
        self.validator = ValidationService()
        
        # Initialize ML components
        self.frame_sampler = FrameSampler(
            sample_rate=self.config['sample_rate']
        )
        
        self.yolo_detector = YOLODetector(
            confidence_threshold=self.config['confidence_threshold'],
            use_real_yolo=self.config['use_real_yolo']
        )
        
        self.tracker = Tracker(
            iou_threshold=self.config['iou_threshold'],
            max_age=self.config['max_age']
        )
        
        self.event_generator = EventIntelligenceService(
            video_fps=self.config['video_fps']
        )
        
        # Initialize embedding models (Phase 10 & 11)
        self.reid_model = PersonReID(
            use_mock=not self.config['use_real_models']
        ) if self.config['generate_reid_embeddings'] else None
        
        self.clip_model = CLIPSearch(
            use_mock=not self.config['use_real_models']
        ) if self.config['generate_clip_embeddings'] else None
        
        logger.info("Pipeline Orchestrator initialized")
        
    def _default_config(self) -> Dict:
        """Default configuration for the pipeline"""
        return {
            'sample_rate': 30,  # Process 1/30 frames for 30x speedup
            'confidence_threshold': 0.5,
            'use_real_yolo': False,
            'use_real_models': False,
            'iou_threshold': 0.3,
            'max_age': 30,
            'video_fps': 30,
            'generate_reid_embeddings': True,
            'generate_clip_embeddings': True,
            'enable_validation': True,
            'enable_error_recovery': True
        }
    
    def process_video(self, video_id: str, db: Session) -> Dict[str, Any]:
        """
        THE SINGLE ENTRY POINT for video processing.
        
        Args:
            video_id: UUID of the video to process
            db: Database session
            
        Returns:
            Processing result with statistics and status
            
        Raises:
            Exception: If processing fails critically
        """
        video_uuid = uuid.UUID(video_id)
        
        try:
            logger.info(f"🎬 Starting video processing: {video_id}")
            
            # Phase 1: Validation
            if self.config['enable_validation']:
                validation_result = self._validate_video(video_uuid, db)
                if not validation_result['valid']:
                    return self._failure_result(
                        video_id, 
                        "validation_failed", 
                        validation_result['reason']
                    )
            
            # Phase 2: Initialize processing state
            self.processing_manager.start_processing(video_id, db)
            
            # Phase 3: Load video
            video = get_video(db, video_id)
            if not video:
                raise ValueError(f"Video not found: {video_id}")
            
            # Phase 4: Execute pipeline
            result = self._execute_pipeline(video, db)
            
            # Phase 5: Mark completion
            self.processing_manager.complete_processing(
                video_id, db, result['stats']
            )
            
            logger.info(f"✅ Video processing completed: {video_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Video processing failed: {video_id} - {str(e)}")
            logger.error(traceback.format_exc())
            
            # Mark as failed
            self.processing_manager.fail_processing(video_id, db, str(e))
            
            if self.config['enable_error_recovery']:
                return self._failure_result(video_id, "processing_failed", str(e))
            else:
                raise
    
    def _validate_video(self, video_id: uuid.UUID, db: Session) -> Dict[str, Any]:
        """Validate video before processing"""
        return self.validator.validate_video_for_processing(video_id, db)
    
    def _execute_pipeline(self, video: Video, db: Session) -> Dict[str, Any]:
        """Execute the complete ML pipeline"""
        
        stats = {
            'frames_processed': 0,
            'total_detections': 0,
            'total_tracks': 0,
            'total_events': 0,
            'reid_embeddings': 0,
            'clip_embeddings': 0,
            'processing_time_seconds': 0
        }
        
        start_time = datetime.now()
        
        try:
            with VideoLoader(video.file_path) as video_loader:
                # Update processing state
                self.processing_manager.set_stage(
                    str(video.id), db, "loading", 
                    "Video loaded successfully"
                )
                
                # Initialize tracking structures
                all_tracks = {}
                frame_embeddings = []
                track_embeddings = {}
                
                # Set total frames for progress tracking
                self.processing_manager.set_total_frames(
                    str(video.id), db, video_loader.total_frames
                )
                
                # Load zones for event intelligence if camera exists
                if video.camera_id:
                    self.event_generator.load_zones(video.camera_id, db)
                
                # Process frames through pipeline
                sampled_frames = self.frame_sampler.sample(video_loader.get_frames())
                
                for frame_number, frame in sampled_frames:
                    stats['frames_processed'] += 1
                    
                    # Update progress every 10 frames
                    if stats['frames_processed'] % 10 == 0:
                        self.processing_manager.update_progress(
                            str(video.id), db, stats['frames_processed']
                        )
                    
                    # YOLO Detection
                    if stats['frames_processed'] == 1:
                        self.processing_manager.set_stage(
                            str(video.id), db, "detecting", "Running YOLO detection"
                        )
                    
                    detections = self.yolo_detector.detect(frame, frame_number)
                    person_detections = self.yolo_detector.filter_persons(detections)
                    stats['total_detections'] += len(person_detections)
                    
                    # Object Tracking
                    if stats['frames_processed'] == 50:  # After some detections
                        self.processing_manager.set_stage(
                            str(video.id), db, "tracking", "Tracking objects"
                        )
                    
                    tracked_objects, lifecycle = self.tracker.update(
                        person_detections, frame_number
                    )
                    
                    # Event Generation
                    if stats['frames_processed'] == 100:
                        self.processing_manager.set_stage(
                            str(video.id), db, "events", "Generating events"
                        )
                    
                    events = self.event_generator.generate_events(
                        tracked_objects, lifecycle, frame_number
                    )
                    stats['total_events'] += len(events)
                    
                    # Re-ID Embedding Generation (Phase 10)
                    if self.reid_model and stats['frames_processed'] == 200:
                        self.processing_manager.set_stage(
                            str(video.id), db, "reid_embeddings", 
                            "Extracting Re-ID embeddings"
                        )
                    
                    if self.reid_model:
                        for obj in tracked_objects:
                            track_id = obj['track_id']
                            if track_id not in track_embeddings:
                                person_crop = self.reid_model.crop_person_from_bbox(
                                    frame, obj['bbox']
                                )
                                embedding = self.reid_model.extract_embedding(person_crop)
                                track_embeddings[track_id] = {
                                    'embedding': embedding,
                                    'frame_number': frame_number,
                                    'bbox': obj['bbox']
                                }
                                stats['reid_embeddings'] += 1
                    
                    # CLIP Embedding Generation (Phase 11)
                    if self.clip_model and stats['frames_processed'] == 300:
                        self.processing_manager.set_stage(
                            str(video.id), db, "clip_embeddings",
                            "Extracting CLIP embeddings"
                        )
                    
                    if self.clip_model:
                        clip_embedding = self.clip_model.extract_image_embedding(frame)
                        frame_embeddings.append({
                            'frame_number': frame_number,
                            'embedding': clip_embedding,
                            'video_id': str(video.id),
                            'tracked_count': len(tracked_objects)
                        })
                        stats['clip_embeddings'] += 1
                    
                    # Save to database (batch operations)
                    self.event_generator.persist_frame_data(
                        db=db,
                        video=video,
                        tracked_objects=tracked_objects,
                        events=events,
                        all_tracks=all_tracks,
                        frame_number=frame_number,
                        frame=frame
                    )
                    
                    # Commit periodically
                    if stats['frames_processed'] % 100 == 0:
                        db.commit()
                
                # Final save operations
                self.processing_manager.set_stage(
                    str(video.id), db, "saving", "Saving to database"
                )
                
                db.commit()  # Final commit
                self._save_embeddings(db, all_tracks, track_embeddings)
                
                stats['total_tracks'] = len(all_tracks)
                stats['processing_time_seconds'] = (
                    datetime.now() - start_time
                ).total_seconds()
                
                return {
                    'status': 'success',
                    'video_id': str(video.id),
                    'stats': stats,
                    'message': 'Video processing completed successfully'
                }
                
        except Exception as e:
            # Rollback transaction on failure
            db.rollback()
            raise e
    
    def _save_pipeline_data(
        self, 
        db: Session, 
        video: Video, 
        tracked_objects: list, 
        events: list, 
        all_tracks: dict
    ) -> None:
        """Legacy method: Use persist_frame_data instead"""
        raise NotImplementedError("Use EventIntelligenceService.persist_frame_data")
    
    def _save_embeddings(
        self, 
        db: Session, 
        all_tracks: dict, 
        track_embeddings: dict
    ) -> None:
        """Save embeddings to database"""
        
        from database.models.embedding import Embedding
        
        for track_id, emb_data in track_embeddings.items():
            if track_id in all_tracks:
                track = all_tracks[track_id]
                
                # Convert numpy array to bytes
                embedding_bytes = emb_data['embedding'].tobytes()
                
                embedding = Embedding(
                    track_id=track.id,
                    vector=embedding_bytes,
                    model_version='pipeline_v1'
                )
                db.add(embedding)
        
        db.commit()
    
    def _failure_result(
        self, 
        video_id: str, 
        error_type: str, 
        reason: str
    ) -> Dict[str, Any]:
        """Generate failure result"""
        return {
            'status': 'failed',
            'video_id': video_id,
            'error_type': error_type,
            'reason': reason,
            'stats': {},
            'message': f'Video processing failed: {reason}'
        }


# Convenience functions for external use
def process_video(video_id: str, db: Session, config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    THE SINGLE ENTRY POINT for video processing.
    
    This is the only function external code should call.
    
    Args:
        video_id: UUID of video to process
        db: Database session
        config: Optional configuration overrides
        
    Returns:
        Processing result with statistics
        
    Example:
        >>> from ml_pipeline.orchestrator import process_video
        >>> from database.session import get_db
        >>> 
        >>> db = next(get_db())
        >>> result = process_video("video-uuid-here", db)
        >>> print(result)
        {
            'status': 'success',
            'video_id': '...',
            'stats': {
                'frames_processed': 300,
                'total_tracks': 15,
                'total_events': 450,
                'processing_time_seconds': 45.2
            }
        }
    """
    orchestrator = PipelineOrchestrator(config)
    return orchestrator.process_video(video_id, db)


def get_processing_status(video_id: str, db: Session) -> Dict[str, Any]:
    """
    Get current processing status for a video
    
    Args:
        video_id: UUID of video
        db: Database session
        
    Returns:
        Current processing status and progress
    """
    processing_manager = ProcessingManager()
    return processing_manager.get_status(video_id, db)