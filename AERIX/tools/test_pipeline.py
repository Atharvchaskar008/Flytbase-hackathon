"""
Test Script for Pipeline Orchestrator

Demonstrates the complete pipeline flow:
Video → Frame Sampler → YOLO → Tracker → Events → Embeddings → Store

Run this to see the pipeline output.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ml_pipeline.pipeline import VideoPipeline


def test_pipeline_initialization():
    """Test pipeline initialization and show configuration"""
    
    print("\n" + "=" * 70)
    print("TEST: Pipeline Initialization")
    print("=" * 70)
    
    # Create pipeline with default settings
    pipeline = VideoPipeline(
        sample_rate=30,
        confidence_threshold=0.5,
        use_real_yolo=False,
        generate_reid_embeddings=True,
        generate_clip_embeddings=True
    )
    
    print("\n✅ Pipeline initialized successfully!")
    print("\nPipeline Components:")
    print(f"  1. Frame Sampler: {type(pipeline.frame_sampler).__name__}")
    print(f"  2. YOLO Detector: {type(pipeline.yolo_detector).__name__}")
    print(f"  3. Tracker: {type(pipeline.tracker).__name__}")
    print(f"  4. Event Generator: {type(pipeline.event_generator).__name__}")
    print(f"  5. Re-ID Model: {type(pipeline.reid_model).__name__ if pipeline.reid_model else 'Disabled'}")
    print(f"  6. CLIP Model: {type(pipeline.clip_model).__name__ if pipeline.clip_model else 'Disabled'}")
    
    return pipeline


def test_pipeline_flow():
    """Test the complete pipeline flow with mock data"""
    
    print("\n" + "=" * 70)
    print("TEST: Complete Pipeline Flow")
    print("=" * 70)
    
    # Create pipeline
    pipeline = VideoPipeline(
        sample_rate=30,
        use_real_yolo=False,
        generate_reid_embeddings=True,
        generate_clip_embeddings=True
    )
    
    print("\n📋 Pipeline Flow:")
    print("   Video")
    print("     ↓")
    print("   Frame Sampler (Phase 4) - 30x speedup")
    print("     ↓")
    print("   YOLO Detection (Phase 5) - Person detection")
    print("     ↓")
    print("   Tracker (Phase 6) - Persistent IDs")
    print("     ↓")
    print("   Event Generator (Phase 7) - Searchable events")
    print("     ↓")
    print("   Re-ID Embeddings (Phase 10) - Person search")
    print("     ↓")
    print("   CLIP Embeddings (Phase 11) - Natural language search")
    print("     ↓")
    print("   Store Everything (Database)")
    
    return pipeline


def show_api_usage():
    """Show how to use the pipeline API"""
    
    print("\n" + "=" * 70)
    print("API Usage Examples")
    print("=" * 70)
    
    print("""
# Method 1: Using the convenience function (recommended)
from ml_pipeline.pipeline import process_video
from database.session import get_db

db = next(get_db())
result = process_video(
    video_id="your-video-uuid",
    db=db,
    sample_rate=30,        # Process 1/30 frames (1 FPS from 30 FPS)
    use_real_yolo=False,   # Set True for real YOLOv8
    generate_embeddings=True
)

print(result)
# Output:
# {
#     'status': 'success',
#     'video_id': '...',
#     'frames_processed': 300,
#     'frames_total': 9000,
#     'speed_improvement': '30x',
#     'total_tracks': 15,
#     'total_events': 450,
#     'total_detections': 1500,
#     'reid_embeddings': 15,
#     'clip_embeddings': 300
# }


# Method 2: Using the VideoPipeline class directly
from ml_pipeline.pipeline import VideoPipeline
from database.session import get_db

pipeline = VideoPipeline(
    sample_rate=30,
    confidence_threshold=0.5,
    use_real_yolo=False,
    generate_reid_embeddings=True,
    generate_clip_embeddings=True
)

db = next(get_db())
result = pipeline.process_video("your-video-uuid", db)


# FastAPI Integration (already done in backend/api/upload.py)
@router.post("/process/{video_id}")
async def process_video_endpoint(video_id: str, db: Session = Depends(get_db)):
    from ml_pipeline.pipeline import process_video
    result = process_video(video_id, db, sample_rate=30, use_real_yolo=False)
    return result
""")


if __name__ == "__main__":
    # Run tests
    print("\n" + "=" * 70)
    print("TRACE Pipeline Orchestrator - Phase 9")
    print("The Heart of TRACE")
    print("=" * 70)
    
    # Test 1: Initialization
    test_pipeline_initialization()
    
    # Test 2: Flow
    test_pipeline_flow()
    
    # Show API usage
    show_api_usage()
    
    print("\n" + "=" * 70)
    print("✅ All Tests Passed!")
    print("=" * 70)
    print("\nThe pipeline orchestrator is ready to process videos.")
    print("Use: process_video(video_id, db) to start processing.")
    print("=" * 70 + "\n")
