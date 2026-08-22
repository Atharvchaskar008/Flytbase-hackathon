"""
Search API - Phase 10 & 11 Implementation

Phase 10: Image Search
POST /search/image - Upload person image, get matching tracks

Phase 11: Natural Language Search  
POST /search/text - Search frames using natural language
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import uuid
import cv2
import numpy as np
from pathlib import Path
import tempfile
import os

from database.session import get_db
from database.models.video import Video
from database.models.track import Track
from database.models.event import Event
from ml_pipeline.reid.person_reid import PersonReID, EmbeddingDatabase
from ml_pipeline.search.clip_search import CLIPSearch, FrameEmbeddingDatabase
from ml_pipeline.detection.yolo_detector import YOLODetector

router = APIRouter()

# Initialize search components (in production, these would be loaded from config)
person_reid = PersonReID(use_mock=True)
clip_search = CLIPSearch(use_mock=True)
yolo_detector = YOLODetector(use_real_yolo=False)

# In-memory databases for demo (in production, use persistent storage)
embedding_db = EmbeddingDatabase()
frame_embedding_db = FrameEmbeddingDatabase()


@router.post("/search/image")
async def search_by_image(
    image: UploadFile = File(...),
    threshold: float = Form(0.7),
    top_k: int = Form(10),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Phase 10: Image Search
    
    Workflow:
    person.jpg → YOLO detects → Crop person → Re-ID Model → Embedding → Compare → Results
    
    Args:
        image: Uploaded person image
        threshold: Similarity threshold (0.0-1.0)
        top_k: Maximum number of results
        
    Returns:
        Search results with matching tracks
    """
    
    # Validate file type
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save uploaded image temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
        content = await image.read()
        tmp_file.write(content)
        tmp_image_path = tmp_file.name
    
    try:
        # Phase 10 workflow
        matches = person_reid.search_person_by_image(
            query_image_path=tmp_image_path,
            stored_embeddings=embedding_db.get_all_embeddings(),
            yolo_detector=yolo_detector,
            threshold=threshold
        )
        
        # Limit results
        matches = matches[:top_k]
        
        # Format response
        results = []
        for match in matches:
            result = {
                "track_id": match['track_id'],
                "camera": match['camera'],
                "timestamp": match['timestamp'],
                "similarity": round(match['similarity'], 4),
                "confidence": round(match.get('query_confidence', 0.0), 2),
                "frame_number": match['frame_number'],
                "bbox": match['bbox']
            }
            results.append(result)
        
        response = {
            "status": "success",
            "query_type": "image_search",
            "results_count": len(results),
            "threshold_used": threshold,
            "results": results
        }
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    
    finally:
        # Cleanup temporary file
        if os.path.exists(tmp_image_path):
            os.unlink(tmp_image_path)


@router.post("/search/text")
async def search_by_text(
    query: str = Form(...),
    threshold: float = Form(0.3),
    top_k: int = Form(20),
    video_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Phase 11: Natural Language Search using CLIP
    
    Workflow:
    "red cap" → CLIP Text Embedding → Cosine Similarity → Matching Frames
    
    Args:
        query: Natural language query (e.g., "red cap", "person in blue shirt")
        threshold: Similarity threshold (0.0-1.0)
        top_k: Maximum number of results
        video_id: Optional video filter
        
    Returns:
        Search results with matching frames
    """
    
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        # Get frame embeddings (filter by video if specified)
        if video_id:
            frame_embeddings = frame_embedding_db.search_by_video(video_id)
        else:
            frame_embeddings = frame_embedding_db.get_all_embeddings()
        
        if not frame_embeddings:
            return {
                "status": "success",
                "query_type": "text_search",
                "query": query,
                "results_count": 0,
                "message": "No frame embeddings available for search",
                "results": []
            }
        
        # Phase 11 workflow
        matches = clip_search.search_by_text(
            query_text=query,
            stored_frame_embeddings=frame_embeddings,
            threshold=threshold,
            top_k=top_k
        )
        
        # Format response
        results = []
        for match in matches:
            result = {
                "frame_number": match['frame_number'],
                "video_id": match['video_id'],
                "timestamp": match['timestamp'],
                "similarity": round(match['similarity'], 4),
                "track_id": match.get('track_id'),
                "description": match['description']
            }
            results.append(result)
        
        response = {
            "status": "success",
            "query_type": "text_search",
            "query": query,
            "results_count": len(results),
            "threshold_used": threshold,
            "video_filter": video_id,
            "results": results
        }
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search/suggestions")
async def get_search_suggestions() -> Dict[str, List[str]]:
    """
    Get search suggestions for natural language queries
    
    Returns:
        Categorized search suggestions
    """
    
    suggestions = {
        "colors": [
            "red shirt", "blue jacket", "black cap", "white shoes",
            "green bag", "yellow hat", "purple clothing", "orange shirt"
        ],
        "clothing": [
            "person in uniform", "man with tie", "woman in dress",
            "child with backpack", "person wearing glasses", "hooded person"
        ],
        "actions": [
            "person walking", "people talking", "someone running",
            "person sitting", "group of people", "person with phone"
        ],
        "objects": [
            "person with bag", "carrying luggage", "person with umbrella",
            "wearing mask", "person with bicycle", "holding something"
        ]
    }
    
    return {
        "status": "success",
        "suggestions": suggestions,
        "total_suggestions": sum(len(category) for category in suggestions.values())
    }


@router.post("/search/process-video")
async def process_video_for_search(
    video_id: str = Form(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process video for search capabilities
    
    This endpoint would:
    1. Extract Re-ID embeddings from tracked persons (Phase 10)
    2. Extract CLIP embeddings from frames (Phase 11)
    
    Args:
        video_id: UUID of video to process
        
    Returns:
        Processing status and statistics
    """
    
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
    
    # Check if video exists
    video = db.query(Video).filter(Video.id == video_uuid).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # In a real implementation, this would:
    # 1. Load video frames
    # 2. Extract Re-ID embeddings from tracked persons
    # 3. Extract CLIP embeddings from all frames
    # 4. Store embeddings in database/vector store
    
    # For demo, simulate processing
    print(f"Processing video {video_id} for search...")
    
    # Simulate adding some embeddings
    mock_reid_embeddings = 5
    mock_clip_embeddings = 20
    
    # Add mock Re-ID embeddings
    for i in range(mock_reid_embeddings):
        mock_embedding = np.random.randn(512)
        mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
        
        embedding_db.add_embedding(
            track_id=i + 1,
            embedding=mock_embedding,
            bbox=[100 + i*50, 100, 50, 120],
            frame_number=(i + 1) * 30,
            timestamp=f"00:{(i+1)*10:02d}",
            camera=video.camera.name if video.camera else "Camera A"
        )
    
    # Add mock CLIP embeddings
    for i in range(mock_clip_embeddings):
        mock_embedding = np.random.randn(512)
        mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
        
        frame_embedding_db.add_frame_embedding(
            frame_number=(i + 1) * 30,
            embedding=mock_embedding,
            video_id=str(video_id),
            timestamp=f"00:{(i+1)*3:02d}"
        )
    
    return {
        "status": "success",
        "video_id": str(video_id),
        "reid_embeddings_added": mock_reid_embeddings,
        "clip_embeddings_added": mock_clip_embeddings,
        "total_reid_embeddings": embedding_db.size(),
        "total_clip_embeddings": frame_embedding_db.size(),
        "message": "Video processed for search capabilities"
    }


@router.get("/search/status")
async def get_search_status() -> Dict[str, Any]:
    """
    Get current search system status
    
    Returns:
        Statistics about available embeddings and search capabilities
    """
    
    return {
        "status": "active",
        "phase_10_reid": {
            "enabled": True,
            "total_embeddings": embedding_db.size(),
            "model_type": "mock" if person_reid.use_mock else "production"
        },
        "phase_11_clip": {
            "enabled": True, 
            "total_frame_embeddings": frame_embedding_db.size(),
            "model_type": "mock" if clip_search.use_mock else "production",
            "model_name": clip_search.model_name
        },
        "search_capabilities": [
            "image_search_by_person",
            "natural_language_frame_search", 
            "similarity_matching",
            "multi_modal_queries"
        ]
    }