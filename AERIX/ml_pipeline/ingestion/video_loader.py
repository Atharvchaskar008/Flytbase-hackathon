"""Video Loader - Loads video from file path"""

import cv2
from pathlib import Path


class VideoLoader:
    """Loads video file and provides access to frames"""
    
    def __init__(self, video_path: str):
        """
        Initialize video loader
        
        Args:
            video_path: Path to video file
        """
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
    def get_frames(self):
        """
        Generator that yields frames one by one
        
        Yields:
            tuple: (frame_number, frame_image)
        """
        frame_number = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            yield frame_number, frame
            frame_number += 1
    
    def release(self):
        """Release video capture resources"""
        if self.cap:
            self.cap.release()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
