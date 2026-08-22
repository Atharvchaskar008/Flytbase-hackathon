#!/usr/bin/env python3
"""Test script for Phase 3 - Video Processing Pipeline"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from ml_pipeline.pipeline import process_video
from database.repository import video_repository


def test_pipeline():
    """Test the video processing pipeline"""
    print("=" * 60)
    print("Phase 3 - Video Processing Pipeline Test")
    print("=" * 60)
    
    # Create database session
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Get the most recent uploaded video
        videos = db.query(video_repository.Video).filter_by(status="uploaded").all()
        
        if not videos:
            print("❌ No uploaded videos found!")
            print("   Please upload a video first using POST /upload/video")
            return
        
        # Use the first uploaded video
        video = videos[0]
        print(f"\n📹 Testing with video:")
        print(f"   ID: {video.id}")
        print(f"   Filename: {video.filename}")
        print(f"   Status: {video.status}")
        print(f"   Path: {video.file_path}")
        
        print("\n" + "=" * 60)
        print("Starting Pipeline Processing...")
        print("=" * 60 + "\n")
        
        # Process the video
        process_video(str(video.id), db)
        
        print("\n" + "=" * 60)
        print("Pipeline Test Complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_pipeline()
