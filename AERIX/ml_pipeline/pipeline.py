"""ML Pipeline Orchestrator - Coordinates the entire video processing pipeline

Phase 9 - The Heart of TRACE:

Video → Frame Sampler → YOLO → Tracker → Generate Events → Generate Embeddings → Store Everything

This is the single entry point for all video processing.
One function: process_video(video_id)
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import numpy as np
from datetime import datetime

from ml_pipeline.ingestion.video_loader import VideoLoader
from ml_pipeline.ingestion.frame_sampler import FrameSampler
from ml_pipeline.detection.yolo_detector import YOLODetector
from ml_pipeline.tracking.tracker import Tracker
from services.event_intelligence_service import EventIntelligenceService
from ml_pipeline.reid.person_reid import PersonReID
from ml_pipeline.search.clip_search import CLIPSearch
from ml_pipeline.progress_tracker import ProgressTracker

from database.repository.video_repository import get_video, update_status
from database.models.track import Track
from database.models.track_history import TrackHistory
from database.models.event import Event
from database.models.embedding import Embedding
import uuid


class VideoPipeline:
    """Orchestrates the ML pipeline for video processing"""
    
    def __init__(
        self,
        sample_rate: int = 30,
        confidence_threshold: float = 0.5,
        use_real_yolo: bool = False,
        generate_reid_embeddings: bool = True,
        generate_clip_embeddings: bool = True
    ):
        """
        Initialize pipeline components
        
        Args:
            sample_rate: Process every Nth frame (default: 30 = 1 FPS from 30 FPS video)
            confidence_threshold: Minimum confidence for detections
            use_real_yolo: Whether to use real YOLO model
            generate_reid_embeddings: Whether to generate Re-ID embeddings (Phase 10)
            generate_clip_embeddings: Whether to generate CLIP embeddings (Phase 11)
        """
        print("\n" + "=" * 60)
        print("TRACE Video Pipeline - Phase 9 Orchestrator")
        print("=" * 60)
        
        # Phase 4: Frame Sampling
        self.frame_sampler = FrameSampler(sample_rate=sample_rate)
        
        # Phase 5: YOLO Detection
        self.yolo_detector = YOLODetector(
            confidence_threshold=confidence_threshold,
            use_real_yolo=use_real_yolo
        )
        
        # Phase 6: Multi-Object Tracking
        self.tracker = Tracker(iou_threshold=0.3, max_age=30)
        
        # Phase 7: Event Intelligence
        self.event_intelligence = EventIntelligenceService(video_fps=30)
        
        # Phase 10: Person Re-ID Embeddings
        self.generate_reid_embeddings = generate_reid_embeddings
        self.reid_model = PersonReID(use_mock=True) if generate_reid_embeddings else None
        
        # Phase 11: CLIP Frame Embeddings
        self.generate_clip_embeddings = generate_clip_embeddings
        self.clip_model = CLIPSearch(use_mock=True) if generate_clip_embeddings else None
        
        # Statistics
        self.stats = {
            'frames_processed': 0,
            'total_detections': 0,
            'total_tracks': 0,
            'total_events': 0,
            'reid_embeddings': 0,
            'clip_embeddings': 0
        }
        
        print(f"[Pipeline] Initialized with configuration:")
        print(f"  - Sample Rate: {sample_rate} (processing 1/{sample_rate} frames)")
        print(f"  - YOLO: {'Real YOLOv8' if use_real_yolo else 'Mock Detector'}")
        print(f"  - Re-ID Embeddings: {'Enabled' if generate_reid_embeddings else 'Disabled'}")
        print(f"  - CLIP Embeddings: {'Enabled' if generate_clip_embeddings else 'Disabled'}")
        print("=" * 60 + "\n")
    
    def process_video(self, video_id: str, db: Session) -> Dict[str, Any]:
        """
        Process video through the ML pipeline
        
        Args:
            video_id: UUID of video to process
            db: Database session
            
        Workflow:
            1. VideoRepository → Get filepath
            2. VideoLoader → Load video
            3. FrameSampler → Sample frames
            4. YOLO → Detect objects
            5. Tracker → Track objects
            6. EventGenerator → Generate events
            7. ReID Model → Generate person embeddings
            8. CLIP Model → Generate frame embeddings
            9. Save Everything to DB
            10. Update Video Status = processed
            
        Returns:
            Dictionary with processing statistics
        """
        # Initialize progress tracker
        progress = ProgressTracker(db, video_id)
        
        try:
            print(f"\n{'=' * 60}")
            print(f"Processing Video: {video_id}")
            print(f"{'=' * 60}\n")
            
            # Step 1: Get video from database
            progress.set_step("loading")
            video = get_video(db, video_id)
            if not video:
                raise ValueError(f"Video not found: {video_id}")
            
            filepath = video.file_path
            print(f"Video path: {filepath}")
            
            # Step 2: Load video
            with VideoLoader(filepath) as video_loader:
                progress.set_total_frames(video_loader.total_frames)
                
                print(f"\n[Step 1/10] Video Loaded")
                print(f"  Total frames: {video_loader.total_frames}")
                print(f"  FPS: {video_loader.fps}")
                print(f"  Resolution: {video_loader.width}x{video_loader.height}")
                
                # Phase 4: Frame Sampling
                progress.set_step("sampling")
                expected_frames = video_loader.total_frames // self.frame_sampler.sample_rate
                print(f"\n[Step 2/10] Frame Sampling")
                print(f"  Sample rate: 1/{self.frame_sampler.sample_rate}")
                print(f"  Expected frames to process: ~{expected_frames}")
                
                # Initialize tracking structures
                all_tracks = {}  # track_id -> Track model
                frame_embeddings = []  # For CLIP embeddings
                track_embeddings = {}  # track_id -> embedding data

                # Load zone polygons for this camera so that entered_zone /
                # exited_zone events fire during frame processing.
                if video.camera_id:
                    zones_loaded = self.event_intelligence.load_zones(video.camera_id, db)
                    if zones_loaded:
                        print(f"  [Zones] Loaded {zones_loaded} zone(s) for camera {video.camera_id}")
                # Step 3: Sample frames and process
                progress.set_step("detecting")
                sampled_frames = self.frame_sampler.sample(video_loader.get_frames())
                
                for frame_number, frame in sampled_frames:
                    self.stats['frames_processed'] += 1
                    
                    # Update progress every 10 frames
                    if self.stats['frames_processed'] % 10 == 0:
                        progress.update_frame_progress(self.stats['frames_processed'])
                    
                    # Step 4: YOLO Detection (Phase 5)
                    detections = self.yolo_detector.detect(frame, frame_number)
                    person_detections = self.yolo_detector.filter_persons(detections)
                    self.stats['total_detections'] += len(person_detections)
                    
                    # Step 5: Tracking (Phase 6)
                    if self.stats['frames_processed'] == 1:
                        progress.set_step("tracking")
                    tracked_objects, lifecycle = self.tracker.update(person_detections, frame_number)
                    
                    # Step 6: Event Intelligence (Phase 7)
                    if self.stats['frames_processed'] == 1:
                        progress.set_step("events")
                    events = self.event_intelligence.generate_events(tracked_objects, lifecycle, frame_number)
                    self.stats['total_events'] += len(events)
                    
                    # Step 7: Generate Re-ID Embeddings (Phase 10)
                    if self.generate_reid_embeddings and self.reid_model:
                        if self.stats['frames_processed'] == 1:
                            progress.set_step("reid")
                        for obj in tracked_objects:
                            track_id = obj['track_id']
                            # Only generate embedding once per track (on first detection)
                            if track_id not in track_embeddings:
                                person_crop = self.reid_model.crop_person_from_bbox(frame, obj['bbox'])
                                embedding = self.reid_model.extract_embedding(person_crop)
                                track_embeddings[track_id] = {
                                    'embedding': embedding,
                                    'frame_number': frame_number,
                                    'bbox': obj['bbox']
                                }
                                self.stats['reid_embeddings'] += 1
                    
                    # Step 8: Generate CLIP Frame Embeddings (Phase 11)
                    if self.generate_clip_embeddings and self.clip_model:
                        if self.stats['frames_processed'] == 1:
                            progress.set_step("clip")
                        # Extract CLIP embedding for the entire frame
                        clip_embedding = self.clip_model.extract_image_embedding(frame)
                        frame_embeddings.append({
                            'frame_number': frame_number,
                            'embedding': clip_embedding,
                            'video_id': str(video_id),
                            'tracked_count': len(tracked_objects)
                        })
                        self.stats['clip_embeddings'] += 1
                    
                    # Console output for progress
                    if self.stats['frames_processed'] % 50 == 0:
                        print(f"  Processed {self.stats['frames_processed']} frames...")
                    
                    # Step 9: Save to database (batch commit every 100 frames)
                    self.event_intelligence.persist_frame_data(
                        db=db,
                        video=video,
                        tracked_objects=tracked_objects,
                        events=events,
                        all_tracks=all_tracks,
                        frame_number=frame_number,
                        frame=frame,
                    )
                    
                    if self.stats['frames_processed'] % 100 == 0:
                        db.commit()
                
                # Final commit for any remaining data
                db.commit()
                
                # Step 9b: Save embeddings to database
                progress.set_step("saving")
                self._save_embeddings(db, all_tracks, track_embeddings)
                
            # Step 10: Mark complete
            progress.complete({
                'total_tracks': len(all_tracks),
                'total_events': self.stats['total_events']
            })
            
            # Calculate final statistics
            sampling_stats = self.frame_sampler.get_stats()
            
            print(f"\n{'=' * 60}")
            print(f"✅ Video Processing Complete!")
            print(f"{'=' * 60}")
            print(f"\n📊 Processing Statistics:")
            print(f"  Total frames in video: {sampling_stats['total']}")
            print(f"  Frames processed: {self.stats['frames_processed']}")
            print(f"  Frames skipped: {sampling_stats['skipped']}")
            print(f"  Speed improvement: {sampling_stats['sample_rate']}x faster")
            print(f"\n📋 Detection Statistics:")
            print(f"  Total detections: {self.stats['total_detections']}")
            print(f"  Total tracks: {len(all_tracks)}")
            print(f"  Total events: {self.stats['total_events']}")
            print(f"\n🔮 Embedding Statistics:")
            print(f"  Re-ID embeddings: {self.stats['reid_embeddings']}")
            print(f"  CLIP frame embeddings: {self.stats['clip_embeddings']}")
            print(f"\n{'=' * 60}\n")
            
            return {
                'status': 'success',
                'video_id': str(video_id),
                'frames_processed': self.stats['frames_processed'],
                'frames_total': sampling_stats['total'],
                'speed_improvement': f"{sampling_stats['sample_rate']}x",
                'total_tracks': len(all_tracks),
                'total_events': self.stats['total_events'],
                'total_detections': self.stats['total_detections'],
                'reid_embeddings': self.stats['reid_embeddings'],
                'clip_embeddings': self.stats['clip_embeddings']
            }
        
        except Exception as e:
            progress.fail(str(e))
            raise
    
    def _save_tracks_and_events(
        self,
        db: Session,
        video,
        tracked_objects: list,
        events: list,
        all_tracks: dict
    ) -> None:
        """Legacy store method retained for compatibility."""
        raise NotImplementedError(
            "Use EventIntelligenceService.persist_frame_data instead of _save_tracks_and_events"
        )
    
    def _save_embeddings(
        self,
        db: Session,
        all_tracks: dict,
        track_embeddings: dict
    ) -> None:
        """
        Save embeddings to database
        
        Args:
            db: Database session
            all_tracks: Dictionary mapping track IDs to Track models
            track_embeddings: Dictionary mapping track IDs to embedding data
        """
        if not track_embeddings:
            return
        
        print(f"\n[Step 9b] Saving Embeddings")
        saved_count = 0
        
        for track_id, emb_data in track_embeddings.items():
            if track_id in all_tracks:
                track = all_tracks[track_id]
                
                # Convert numpy array to bytes for storage
                embedding_bytes = emb_data['embedding'].tobytes()
                
                embedding = Embedding(
                    track_id=track.id,
                    vector=embedding_bytes,
                    model_version='mock_reid_v1'
                )
                db.add(embedding)
                saved_count += 1
        
        db.commit()
        print(f"  Saved {saved_count} Re-ID embeddings to database")


def process_video(
    video_id: str, 
    db: Session, 
    sample_rate: int = 30, 
    use_real_yolo: bool = False,
    generate_embeddings: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to process a video
    
    Args:
        video_id: UUID of video to process
        db: Database session
        sample_rate: Process every Nth frame (default: 30 = 1 FPS from 30 FPS video)
        use_real_yolo: Whether to use real YOLO model
        generate_embeddings: Whether to generate Re-ID and CLIP embeddings
        
    Returns:
        Dictionary with processing statistics
        
    Pipeline Flow:
        Video
        ↓
        Frame Sampler (Phase 4) - 30x speedup
        ↓
        YOLO Detection (Phase 5) - Person detection
        ↓
        Tracker (Phase 6) - Persistent IDs across frames
        ↓
        Event Generator (Phase 7) - Searchable events
        ↓
        Re-ID Embeddings (Phase 10) - Person search
        ↓
        CLIP Embeddings (Phase 11) - Natural language search
        ↓
        Store Everything (Database)
        
    Example:
        >>> from database.session import get_db
        >>> from ml_pipeline.pipeline import process_video
        >>> 
        >>> db = next(get_db())
        >>> result = process_video("video-uuid-here", db)
        >>> print(result)
        {
            'status': 'success',
            'video_id': '...',
            'frames_processed': 300,
            'total_tracks': 15,
            'total_events': 450,
            'reid_embeddings': 15,
            'clip_embeddings': 300
        }
    """
    pipeline = VideoPipeline(
        sample_rate=sample_rate, 
        confidence_threshold=0.5,
        use_real_yolo=use_real_yolo,
        generate_reid_embeddings=generate_embeddings,
        generate_clip_embeddings=generate_embeddings
    )
    return pipeline.process_video(video_id, db)
