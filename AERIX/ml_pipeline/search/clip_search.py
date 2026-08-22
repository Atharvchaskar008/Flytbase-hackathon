"""
CLIP-based Natural Language Search - Phase 11 Implementation

Workflow:
Video Processing → Every Sampled Frame → CLIP Image Embedding → Store pgvector

Later:
"red cap" → CLIP Text Embedding → Cosine Similarity → Matching Frames

Features:
- CLIP embeddings for images and text
- Natural language search without retraining YOLO
- Frame-level search with descriptions
- Similarity matching with pgvector storage
"""

import numpy as np
import cv2
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

# Handle optional dependencies gracefully
try:
    import torch
    import clip
    TORCH_AVAILABLE = True
    CLIP_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    CLIP_AVAILABLE = False
    print("[CLIPSearch] Warning: PyTorch/CLIP not available, using mock mode only")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[CLIPSearch] Warning: PIL not available, using mock mode only")


class CLIPSearch:
    """CLIP-based natural language search for video frames"""
    
    def __init__(self, model_name: str = "ViT-B/32", use_mock: bool = True):
        """
        Initialize CLIP model for natural language search
        
        Args:
            model_name: CLIP model variant
            use_mock: Whether to use mock embeddings for testing
        """
        # Force mock mode if dependencies not available
        if not TORCH_AVAILABLE or not CLIP_AVAILABLE or not PIL_AVAILABLE:
            use_mock = True
        
        self.use_mock = use_mock
        self.model_name = model_name
        
        if TORCH_AVAILABLE:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        if not use_mock and TORCH_AVAILABLE and CLIP_AVAILABLE:
            self._load_clip_model()
        
        print(f"[CLIPSearch] Initialized (Model: {model_name}, Mock mode: {use_mock})")
    
    def _load_clip_model(self):
        """Load CLIP model"""
        try:
            self.model, self.preprocess = clip.load(self.model_name, device=self.device)
            print(f"[CLIPSearch] Loaded {self.model_name} on {self.device}")
        except Exception as e:
            print(f"[CLIPSearch] Warning: Could not load CLIP model: {e}")
            print("[CLIPSearch] Falling back to mock mode")
            self.use_mock = True
    
    def extract_image_embedding(self, frame: np.ndarray) -> np.ndarray:
        """
        Extract CLIP image embedding from frame
        
        Args:
            frame: Video frame (numpy array)
            
        Returns:
            CLIP image embedding (512-dim for ViT-B/32)
        """
        if self.use_mock:
            return self._extract_image_embedding_mock(frame)
        
        # Convert BGR to RGB
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame_rgb = frame
        
        # Convert to PIL Image and preprocess
        pil_image = Image.fromarray(frame_rgb)
        image_tensor = self.preprocess(pil_image).unsqueeze(0).to(self.device)
        
        # Extract CLIP features
        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)  # Normalize
            embedding = image_features.cpu().numpy().flatten()
        
        return embedding
    
    def _extract_image_embedding_mock(self, frame: np.ndarray) -> np.ndarray:
        """Mock image embedding extraction"""
        height, width = frame.shape[:2]
        
        # Generate deterministic embedding based on frame characteristics
        np.random.seed(int(np.mean(frame) * height * width) % 2**16)
        
        # 512-dimensional embedding (like ViT-B/32)
        embedding = np.random.randn(512)
        
        # Add structure based on image properties
        avg_color = np.mean(frame, axis=(0, 1)) if len(frame.shape) == 3 else [np.mean(frame)]
        
        # Color-based features
        if len(avg_color) == 3:
            embedding[:3] = avg_color / 255.0  # RGB features
        
        # Texture features (simplified)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        embedding[3] = edge_density
        
        # Brightness and contrast
        embedding[4] = np.mean(gray) / 255.0
        embedding[5] = np.std(gray) / 255.0
        
        # L2 normalize
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def extract_text_embedding(self, text: str) -> np.ndarray:
        """
        Extract CLIP text embedding from natural language query
        
        Args:
            text: Natural language description (e.g., "red cap", "person in blue shirt")
            
        Returns:
            CLIP text embedding (512-dim for ViT-B/32)
        """
        if self.use_mock:
            return self._extract_text_embedding_mock(text)
        
        # Tokenize text
        text_tokens = clip.tokenize([text]).to(self.device)
        
        # Extract CLIP text features
        with torch.no_grad():
            text_features = self.model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)  # Normalize
            embedding = text_features.cpu().numpy().flatten()
        
        return embedding
    
    def _extract_text_embedding_mock(self, text: str) -> np.ndarray:
        """Mock text embedding extraction"""
        # Generate deterministic embedding based on text
        text_hash = hash(text.lower()) % 2**16
        np.random.seed(text_hash)
        
        # 512-dimensional embedding
        embedding = np.random.randn(512)
        
        # Add semantic structure based on keywords
        color_keywords = {
            'red': [1.0, 0.0, 0.0], 'blue': [0.0, 0.0, 1.0], 'green': [0.0, 1.0, 0.0],
            'yellow': [1.0, 1.0, 0.0], 'black': [0.0, 0.0, 0.0], 'white': [1.0, 1.0, 1.0],
            'orange': [1.0, 0.5, 0.0], 'purple': [1.0, 0.0, 1.0], 'pink': [1.0, 0.5, 0.5]
        }
        
        object_keywords = {
            'person': 0.9, 'man': 0.8, 'woman': 0.8, 'child': 0.7,
            'shirt': 0.6, 'cap': 0.5, 'hat': 0.5, 'jacket': 0.6,
            'car': 0.4, 'bike': 0.3, 'bag': 0.4
        }
        
        # Color features (first 3 dimensions)
        for color, rgb in color_keywords.items():
            if color in text.lower():
                embedding[:3] = np.array(rgb)
                break
        
        # Object features
        for obj, weight in object_keywords.items():
            if obj in text.lower():
                embedding[10] = weight
                break
        
        # L2 normalize
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def search_by_text(
        self, 
        query_text: str, 
        stored_frame_embeddings: List[Dict[str, Any]],
        threshold: float = 0.3,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search frames using natural language query
        
        Args:
            query_text: Natural language query (e.g., "red cap")
            stored_frame_embeddings: Database of frame embeddings
            threshold: Similarity threshold
            top_k: Maximum number of results
            
        Returns:
            List of matching frames sorted by similarity
        """
        print(f"🔍 Phase 11: Searching for '{query_text}'")
        
        # Extract text embedding
        print("   Step 1: Extracting CLIP text embedding...")
        query_embedding = self.extract_text_embedding(query_text)
        print(f"      Text embedding shape: {query_embedding.shape}")
        
        # Compare with stored frame embeddings
        print("   Step 2: Comparing with stored frame embeddings...")
        matches = []
        
        for stored in stored_frame_embeddings:
            frame_embedding = stored['embedding']
            
            # Calculate cosine similarity
            similarity = np.dot(query_embedding, frame_embedding)
            
            if similarity >= threshold:
                match = {
                    'frame_number': stored['frame_number'],
                    'video_id': stored.get('video_id', 'Unknown'),
                    'timestamp': stored.get('timestamp', 'Unknown'),
                    'similarity': float(similarity),
                    'bbox': stored.get('bbox', []),
                    'track_id': stored.get('track_id'),
                    'description': query_text
                }
                matches.append(match)
        
        # Sort by similarity (highest first) and limit results
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        matches = matches[:top_k]
        
        print(f"   ✅ Found {len(matches)} matching frames")
        
        return matches
    
    def process_video_frames_for_search(
        self, 
        video_frames: List[Tuple[int, np.ndarray]], 
        video_id: str = "unknown"
    ) -> List[Dict[str, Any]]:
        """
        Process video frames and extract CLIP embeddings for later search
        
        Args:
            video_frames: List of (frame_number, frame) tuples
            video_id: Video identifier
            
        Returns:
            List of frame embeddings with metadata
        """
        print(f"📊 Phase 11: Processing {len(video_frames)} frames for CLIP search")
        
        frame_embeddings = []
        
        for i, (frame_number, frame) in enumerate(video_frames):
            if i % 10 == 0:
                print(f"   Processing frame {frame_number} ({i+1}/{len(video_frames)})")
            
            # Extract CLIP image embedding
            embedding = self.extract_image_embedding(frame)
            
            # Store with metadata
            frame_data = {
                'frame_number': frame_number,
                'video_id': video_id,
                'embedding': embedding,
                'timestamp': f"{frame_number // 30:02d}:{(frame_number % 30):02d}",  # Assume 30 FPS
                'processed_at': str(np.datetime64('now'))
            }
            
            frame_embeddings.append(frame_data)
        
        print(f"   ✅ Processed {len(frame_embeddings)} frame embeddings")
        
        return frame_embeddings


class FrameEmbeddingDatabase:
    """Database for storing CLIP frame embeddings"""
    
    def __init__(self):
        self.frame_embeddings = []
        print("[FrameEmbeddingDatabase] Initialized")
    
    def add_frame_embedding(
        self, 
        frame_number: int, 
        embedding: np.ndarray, 
        video_id: str = "unknown",
        timestamp: str = "00:00",
        bbox: Optional[List[float]] = None,
        track_id: Optional[int] = None
    ):
        """Add frame embedding to database"""
        entry = {
            'frame_number': frame_number,
            'video_id': video_id,
            'embedding': embedding,
            'timestamp': timestamp,
            'bbox': bbox or [],
            'track_id': track_id
        }
        self.frame_embeddings.append(entry)
    
    def add_batch_embeddings(self, embeddings: List[Dict[str, Any]]):
        """Add batch of embeddings"""
        self.frame_embeddings.extend(embeddings)
        print(f"   Added {len(embeddings)} frame embeddings to database")
    
    def get_all_embeddings(self) -> List[Dict[str, Any]]:
        """Get all stored frame embeddings"""
        return self.frame_embeddings
    
    def search_by_video(self, video_id: str) -> List[Dict[str, Any]]:
        """Get embeddings for specific video"""
        return [emb for emb in self.frame_embeddings if emb.get('video_id') == video_id]
    
    def clear(self):
        """Clear all embeddings"""
        self.frame_embeddings.clear()
    
    def size(self) -> int:
        """Get number of stored embeddings"""
        return len(self.frame_embeddings)


# Utility functions for Phase 11

def simulate_natural_language_queries() -> List[str]:
    """Get sample natural language queries for testing"""
    return [
        "red cap",
        "person in blue shirt", 
        "woman walking",
        "man with bag",
        "child playing",
        "black jacket",
        "white car",
        "people talking",
        "person running",
        "green clothing"
    ]


def demonstrate_clip_search_workflow():
    """Demonstrate the complete CLIP search workflow"""
    print("\n" + "="*60)
    print("CLIP NATURAL LANGUAGE SEARCH DEMONSTRATION")
    print("="*60)
    
    # Initialize CLIP search
    clip_search = CLIPSearch(use_mock=True)
    db = FrameEmbeddingDatabase()
    
    # Simulate some video frames (mock data)
    print("\n📹 Simulating video frame processing...")
    mock_frames = [
        (30, np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)),    # Frame 30
        (60, np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)),    # Frame 60  
        (90, np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)),    # Frame 90
        (120, np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)),   # Frame 120
    ]
    
    # Process frames for search
    frame_embeddings = clip_search.process_video_frames_for_search(mock_frames, "test_video")
    db.add_batch_embeddings(frame_embeddings)
    
    # Test natural language queries
    queries = ["red cap", "person walking", "blue shirt"]
    
    print(f"\n🔍 Testing natural language search...")
    for query in queries:
        print(f"\nQuery: '{query}'")
        results = clip_search.search_by_text(query, db.get_all_embeddings(), threshold=0.2)
        
        print(f"Results: {len(results)} matches")
        for i, result in enumerate(results[:3]):  # Show top 3
            print(f"  {i+1}. Frame {result['frame_number']} - Similarity: {result['similarity']:.3f}")
    
    return clip_search, db