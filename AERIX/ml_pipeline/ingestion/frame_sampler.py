"""Frame Sampler - Samples frames at specified intervals

Phase 4 Implementation:
- Process 1 FPS instead of 30 FPS (30x speedup)
- Example: 9000 frames → 300 frames processed
"""


class FrameSampler:
    """Samples frames from video stream at regular intervals"""
    
    def __init__(self, sample_rate: int = 1, target_fps: int = None, video_fps: int = None):
        """
        Initialize frame sampler
        
        Args:
            sample_rate: Sample every Nth frame (default: 1 = every frame)
            target_fps: Desired processing FPS (alternative to sample_rate)
            video_fps: Video FPS (required if using target_fps)
            
        Example:
            - Video at 30 FPS, process at 1 FPS: FrameSampler(target_fps=1, video_fps=30)
            - This will sample every 30th frame
        """
        if target_fps and video_fps:
            # Calculate sample_rate from target FPS
            self.sample_rate = int(video_fps / target_fps)
            print(f"[FrameSampler] Processing {target_fps} FPS from {video_fps} FPS video")
            print(f"[FrameSampler] Sampling every {self.sample_rate} frames")
        else:
            self.sample_rate = sample_rate
        
        self.frames_sampled = 0
        self.frames_skipped = 0
    
    def sample(self, frames_generator):
        """
        Sample frames from generator
        
        Args:
            frames_generator: Generator yielding (frame_number, frame)
            
        Yields:
            tuple: (frame_number, frame) for sampled frames
        """
        for frame_number, frame in frames_generator:
            if frame_number % self.sample_rate == 0:
                self.frames_sampled += 1
                yield frame_number, frame
            else:
                self.frames_skipped += 1
    
    def get_stats(self):
        """Get sampling statistics"""
        return {
            'sampled': self.frames_sampled,
            'skipped': self.frames_skipped,
            'total': self.frames_sampled + self.frames_skipped,
            'sample_rate': self.sample_rate
        }
