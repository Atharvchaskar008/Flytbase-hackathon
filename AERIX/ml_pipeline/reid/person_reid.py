"""
Person Re-Identification Model - Phase 10 Implementation

Workflow:
person.jpg → YOLO detects → Crop person → Re-ID Model → Embedding → Compare → Results

Features:
- Person detection and cropping
- Re-ID embedding extraction
- Similarity matching with stored embeddings
- Track matching with confidence scores
"""

import numpy as np
import cv2
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

# Handle optional dependencies gracefully
try:
    import torch
    import torchvision.transforms as transforms
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("[PersonReID] Warning: PyTorch not available, using mock mode only")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[PersonReID] Warning: PIL not available, using mock mode only")


class PersonReID:
    """Person Re-Identification for image search"""
    
    def __init__(self, model_path: Optional[str] = None, use_mock: bool = True):
        """
        Initialize Person Re-ID model
        
        Args:
            model_path: Path to trained Re-ID model
            use_mock: Whether to use mock embeddings for testing
        """
        # Force mock mode if dependencies not available
        if not TORCH_AVAILABLE or not PIL_AVAILABLE:
            use_mock = True
        
        self.use_mock = use_mock
        self.model_path = model_path
        
        if TORCH_AVAILABLE:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            
            # Image preprocessing
            if PIL_AVAILABLE:
                self.transform = transforms.Compose([
                    transforms.Resize((256, 128)),  # Standard Re-ID input size
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                ])
        
        if not use_mock and TORCH_AVAILABLE:
            self._load_model()
        
        print(f"[PersonReID] Initialized (Mock mode: {use_mock})")
    
    def _load_model(self):
        """Load the actual Re-ID model"""
        # In production, load a trained Re-ID model like:
        # - OSNet
        # - ResNet50 with triplet loss
        # - FastReID
        # - Torchreid models
        
        # For now, placeholder for actual model loading
        # self.model = torch.load(self.model_path)
        # self.model.eval()
        pass
    
    def extract_embedding(self, person_crop: np.ndarray) -> np.ndarray:
        """
        Extract Re-ID embedding from person crop
        
        Args:
            person_crop: Cropped person image (numpy array)
            
        Returns:
            Feature embedding vector (512-dim)
        """
        if self.use_mock or not TORCH_AVAILABLE or not PIL_AVAILABLE:
            return self._extract_embedding_mock(person_crop)
        
        # Convert to PIL Image and apply transforms
        if len(person_crop.shape) == 3:
            person_crop = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
        
        pil_image = Image.fromarray(person_crop)
        tensor_image = self.transform(pil_image).unsqueeze(0).to(self.device)
        
        # Extract features using actual model
        with torch.no_grad():
            embedding = self.model(tensor_image)
            embedding = embedding.cpu().numpy().flatten()
        
        # L2 normalize
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def _extract_embedding_mock(self, person_crop: np.ndarray) -> np.ndarray:
        """Mock embedding extraction for testing"""
        height, width = person_crop.shape[:2]
        
        # Generate deterministic embedding based on image characteristics
        # This ensures consistent embeddings for the same input
        np.random.seed(int(height * width * 1000) % 2**16)
        
        # 512-dimensional embedding
        embedding = np.random.randn(512)
        
        # Add some structure based on image properties
        avg_intensity = np.mean(person_crop) / 255.0
        embedding[:50] *= avg_intensity  # Brightness feature
        
        # L2 normalize
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def crop_person_from_bbox(self, image: np.ndarray, bbox: List[float]) -> np.ndarray:
        """
        Crop person from image using bounding box
        
        Args:
            image: Full image (numpy array)
            bbox: [x, y, width, height]
            
        Returns:
            Cropped person image
        """
        x, y, w, h = map(int, bbox)
        
        # Add some padding
        padding = 0.1
        pad_w = int(w * padding)
        pad_h = int(h * padding)
        
        # Expand bbox with padding
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(image.shape[1], x + w + pad_w)
        y2 = min(image.shape[0], y + h + pad_h)
        
        # Crop the person
        person_crop = image[y1:y2, x1:x2]
        
        # Check if crop is valid
        if person_crop.size == 0 or person_crop.shape[0] == 0 or person_crop.shape[1] == 0:
            # Return a default small crop if invalid
            person_crop = np.random.randint(0, 255, (128, 64, 3), dtype=np.uint8)
        
        # Resize to standard size if too small
        if person_crop.shape[0] < 64 or person_crop.shape[1] < 32:
            person_crop = cv2.resize(person_crop, (64, 128))
        
        return person_crop
    
    def compare_embeddings(
        self, 
        query_embedding: np.ndarray, 
        stored_embeddings: List[Dict[str, Any]],
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Compare query embedding with stored embeddings
        
        Args:
            query_embedding: Query person embedding
            stored_embeddings: List of stored embeddings with metadata
            threshold: Similarity threshold (default: 0.7)
            
        Returns:
            List of matches sorted by similarity score
        """
        matches = []
        
        for stored in stored_embeddings:
            stored_emb = stored['embedding']
            
            # Calculate cosine similarity
            similarity = np.dot(query_embedding, stored_emb)
            
            if similarity >= threshold:
                match = {
                    'track_id': stored['track_id'],
                    'camera': stored.get('camera', 'Unknown'),
                    'timestamp': stored.get('timestamp', 'Unknown'),
                    'similarity': float(similarity),
                    'bbox': stored.get('bbox', [0, 0, 0, 0]),
                    'frame_number': stored.get('frame_number', 0)
                }
                matches.append(match)
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        return matches
    
    def search_person_by_image(
        self, 
        query_image_path: str, 
        stored_embeddings: List[Dict[str, Any]],
        yolo_detector,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Complete Phase 10 workflow: Image → Person Detection → Embedding → Search
        
        Args:
            query_image_path: Path to query image
            stored_embeddings: Database of stored embeddings
            yolo_detector: YOLO detector instance
            threshold: Similarity threshold
            
        Returns:
            List of matching tracks with similarity scores
        """
        print(f"🔍 Phase 10: Searching for person in {query_image_path}")
        
        # Load query image
        query_image = cv2.imread(query_image_path)
        if query_image is None:
            raise ValueError(f"Could not load image: {query_image_path}")
        
        print("   Step 1: YOLO person detection...")
        
        # YOLO detection
        detections = yolo_detector.detect(query_image, frame_number=0)
        person_detections = yolo_detector.filter_persons(detections)
        
        if not person_detections:
            print("   ❌ No persons detected in image")
            return []
        
        print(f"   ✅ Found {len(person_detections)} persons")
        
        all_matches = []
        
        for i, detection in enumerate(person_detections):
            print(f"   Step 2: Processing person {i+1}...")
            
            # Crop person
            person_crop = self.crop_person_from_bbox(query_image, detection['bbox'])
            print(f"      Cropped person: {person_crop.shape}")
            
            # Extract embedding
            print("   Step 3: Extracting Re-ID embedding...")
            query_embedding = self.extract_embedding(person_crop)
            print(f"      Embedding shape: {query_embedding.shape}")
            
            # Compare with stored embeddings
            print("   Step 4: Comparing with stored embeddings...")
            matches = self.compare_embeddings(query_embedding, stored_embeddings, threshold)
            
            # Add query info to matches
            for match in matches:
                match['query_person_idx'] = i
                match['query_bbox'] = detection['bbox']
                match['query_confidence'] = detection['confidence']
            
            all_matches.extend(matches)
        
        # Remove duplicates and sort by similarity
        unique_matches = {}
        for match in all_matches:
            key = (match['track_id'], match['frame_number'])
            if key not in unique_matches or match['similarity'] > unique_matches[key]['similarity']:
                unique_matches[key] = match
        
        final_matches = list(unique_matches.values())
        final_matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        print(f"   ✅ Found {len(final_matches)} matching tracks")
        
        return final_matches


class EmbeddingDatabase:
    """Simple in-memory database for storing Re-ID embeddings"""
    
    def __init__(self):
        self.embeddings = []
        print("[EmbeddingDatabase] Initialized")
    
    def add_embedding(
        self, 
        track_id: int, 
        embedding: np.ndarray, 
        bbox: List[float],
        frame_number: int,
        timestamp: str = "Unknown",
        camera: str = "Camera A"
    ):
        """Add embedding to database"""
        entry = {
            'track_id': track_id,
            'embedding': embedding,
            'bbox': bbox,
            'frame_number': frame_number,
            'timestamp': timestamp,
            'camera': camera
        }
        self.embeddings.append(entry)
    
    def get_all_embeddings(self) -> List[Dict[str, Any]]:
        """Get all stored embeddings"""
        return self.embeddings
    
    def clear(self):
        """Clear all embeddings"""
        self.embeddings.clear()
    
    def size(self) -> int:
        """Get number of stored embeddings"""
        return len(self.embeddings)