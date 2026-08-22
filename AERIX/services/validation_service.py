"""
Validation Service for Video Processing

Part of Phase 14 - Processing Manager
Ensures only valid videos enter the processing pipeline.
"""

import uuid
import logging
import cv2
from pathlib import Path
from typing import Dict, Any
from sqlalchemy.orm import Session

from database.repository.video_repository import get_video

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Validates videos before processing
    
    Validation checks:
    1. Video file exists
    2. Video format is supported
    3. Video is not corrupted
    4. Video has valid dimensions
    5. Video has valid frame rate
    6. Video is not empty
    """
    
    def __init__(self):
        """Initialize validation service"""
        self.supported_formats = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
        self.min_resolution = (320, 240)
        self.max_resolution = (7680, 4320)  # 8K
        self.min_fps = 1
        self.max_fps = 120
        self.min_duration = 1  # seconds
        self.max_duration = 7200  # 2 hours
    
    def validate_video_for_processing(
        self, 
        video_id: uuid.UUID, 
        db: Session
    ) -> Dict[str, Any]:
        """
        Validate video for processing
        
        Args:
            video_id: UUID of video to validate
            db: Database session
            
        Returns:
            Validation result with details
        """
        try:
            # Get video from database
            video = get_video(db, str(video_id))
            if not video:
                return {
                    'valid': False,
                    'reason': 'Video not found in database',
                    'error_code': 'VIDEO_NOT_FOUND'
                }
            
            video_path = Path(video.file_path)
            
            # Check if file exists
            if not video_path.exists():
                return {
                    'valid': False,
                    'reason': f'Video file not found: {video_path}',
                    'error_code': 'FILE_NOT_FOUND'
                }
            
            # Check file size
            file_size = video_path.stat().st_size
            if file_size == 0:
                return {
                    'valid': False,
                    'reason': 'Video file is empty',
                    'error_code': 'EMPTY_FILE'
                }
            
            # Check file extension
            if video_path.suffix.lower() not in self.supported_formats:
                return {
                    'valid': False,
                    'reason': f'Unsupported format: {video_path.suffix}',
                    'error_code': 'UNSUPPORTED_FORMAT'
                }
            
            # Validate video properties using OpenCV
            validation_result = self._validate_video_properties(video_path)
            if not validation_result['valid']:
                return validation_result
            
            logger.info(f"✅ Video validation passed: {video_id}")
            return {
                'valid': True,
                'reason': 'Video passed all validation checks',
                'properties': validation_result.get('properties', {})
            }
            
        except Exception as e:
            logger.error(f"Validation error for video {video_id}: {e}")
            return {
                'valid': False,
                'reason': f'Validation failed with error: {str(e)}',
                'error_code': 'VALIDATION_ERROR'
            }
    
    def _validate_video_properties(self, video_path: Path) -> Dict[str, Any]:
        """
        Validate video properties using OpenCV
        
        Args:
            video_path: Path to video file
            
        Returns:
            Validation result with video properties
        """
        try:
            # Open video file
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                return {
                    'valid': False,
                    'reason': 'Cannot open video file - may be corrupted',
                    'error_code': 'CORRUPTED_FILE'
                }
            
            # Get video properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate duration
            duration = frame_count / fps if fps > 0 else 0
            
            # Close video
            cap.release()
            
            # Validate resolution
            if width < self.min_resolution[0] or height < self.min_resolution[1]:
                return {
                    'valid': False,
                    'reason': f'Resolution too low: {width}x{height} (min: {self.min_resolution[0]}x{self.min_resolution[1]})',
                    'error_code': 'RESOLUTION_TOO_LOW'
                }
            
            if width > self.max_resolution[0] or height > self.max_resolution[1]:
                return {
                    'valid': False,
                    'reason': f'Resolution too high: {width}x{height} (max: {self.max_resolution[0]}x{self.max_resolution[1]})',
                    'error_code': 'RESOLUTION_TOO_HIGH'
                }
            
            # Validate FPS
            if fps < self.min_fps or fps > self.max_fps:
                return {
                    'valid': False,
                    'reason': f'Invalid FPS: {fps} (valid range: {self.min_fps}-{self.max_fps})',
                    'error_code': 'INVALID_FPS'
                }
            
            # Validate duration
            if duration < self.min_duration:
                return {
                    'valid': False,
                    'reason': f'Video too short: {duration}s (min: {self.min_duration}s)',
                    'error_code': 'VIDEO_TOO_SHORT'
                }
            
            if duration > self.max_duration:
                return {
                    'valid': False,
                    'reason': f'Video too long: {duration}s (max: {self.max_duration}s)',
                    'error_code': 'VIDEO_TOO_LONG'
                }
            
            # Validate frame count
            if frame_count == 0:
                return {
                    'valid': False,
                    'reason': 'Video has no frames',
                    'error_code': 'NO_FRAMES'
                }
            
            # Try to read first frame to ensure video is readable
            cap = cv2.VideoCapture(str(video_path))
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return {
                    'valid': False,
                    'reason': 'Cannot read video frames - may be corrupted',
                    'error_code': 'UNREADABLE_FRAMES'
                }
            
            return {
                'valid': True,
                'properties': {
                    'width': width,
                    'height': height,
                    'fps': fps,
                    'frame_count': frame_count,
                    'duration_seconds': duration,
                    'file_size_mb': round(video_path.stat().st_size / (1024 * 1024), 2)
                }
            }
            
        except Exception as e:
            return {
                'valid': False,
                'reason': f'Error reading video properties: {str(e)}',
                'error_code': 'PROPERTY_READ_ERROR'
            }
    
    def validate_upload_file(self, file_path: Path, filename: str) -> Dict[str, Any]:
        """
        Validate uploaded file before saving
        
        Args:
            file_path: Path to uploaded file
            filename: Original filename
            
        Returns:
            Validation result
        """
        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.supported_formats:
            return {
                'valid': False,
                'reason': f'Unsupported file format: {file_ext}. Supported: {", ".join(self.supported_formats)}',
                'error_code': 'UNSUPPORTED_FORMAT'
            }
        
        # Check file size
        if not file_path.exists():
            return {
                'valid': False,
                'reason': 'Uploaded file not found',
                'error_code': 'FILE_NOT_FOUND'
            }
        
        file_size = file_path.stat().st_size
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        
        if file_size == 0:
            return {
                'valid': False,
                'reason': 'Uploaded file is empty',
                'error_code': 'EMPTY_FILE'
            }
        
        if file_size > max_size:
            return {
                'valid': False,
                'reason': f'File too large: {file_size / (1024*1024*1024):.1f}GB (max: 2GB)',
                'error_code': 'FILE_TOO_LARGE'
            }
        
        return {
            'valid': True,
            'reason': 'File passed upload validation',
            'file_size': file_size
        }