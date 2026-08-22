"""YOLO Detector - Object detection using YOLO model

Phase 5 Implementation:
- Input: Frame
- Output: [Person, Confidence, Bounding Box]
- Example: Frame 100 → Person 0.96 (120, 240, 400, 600)
"""

from typing import List, Dict, Any
import numpy as np


class YOLODetector:
    """YOLO-based object detector for person and traffic detection
    
    AERIX Extension:
        Supports multi-class traffic detection via detect_traffic().
        COCO classes supported: person, bicycle, car, motorcycle, bus, truck.
        NOTE: COCO does NOT distinguish LGV/HGV. The 'truck' class covers
        all truck types (pickups through 18-wheelers).
    """
    
    # Traffic-relevant COCO class IDs and their labels
    TRAFFIC_COCO_IDS = {0, 1, 2, 3, 5, 7}
    COCO_ID_TO_TRAFFIC = {
        0: 'person',
        1: 'bicycle',
        2: 'car',
        3: 'motorcycle',
        5: 'bus',
        7: 'truck',
    }
    
    def __init__(self, model_path: str = None, confidence_threshold: float = 0.5, use_real_yolo: bool = False):
        """
        Initialize YOLO detector
        
        Args:
            model_path: Path to YOLO model (optional, uses default if None)
            confidence_threshold: Minimum confidence for detections
            use_real_yolo: Whether to use real YOLO model (requires ultralytics)
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.use_real_yolo = use_real_yolo
        
        if use_real_yolo:
            try:
                from ultralytics import YOLO
                # Load YOLOv8 model
                model_name = model_path if model_path else 'yolov8n.pt'
                self.model = YOLO(model_name)
                print(f"[YOLO] Loaded real YOLO model: {model_name}")
            except ImportError:
                print("[YOLO] Warning: ultralytics not installed, using mock detector")
                self.use_real_yolo = False
        
        print(f"[YOLO] Initialized with confidence threshold: {confidence_threshold}")
        print(f"[YOLO] Mode: {'Real YOLO' if self.use_real_yolo else 'Mock Detector'}")
    
    def detect(self, frame: np.ndarray, frame_number: int = None) -> List[Dict[str, Any]]:
        """
        Detect objects in frame
        
        Args:
            frame: Image frame as numpy array
            frame_number: Frame number (for logging)
            
        Returns:
            List of detections, each containing:
                - bbox: [x, y, width, height]
                - confidence: detection confidence
                - class_label: object class (e.g., 'person')
        
        Output Format (Phase 5):
            Frame 100 → Person 0.96 (120, 240, 400, 600)
        """
        if self.use_real_yolo and self.model:
            return self._detect_real_yolo(frame, frame_number)
        else:
            return self._detect_mock(frame, frame_number)
    
    def _detect_real_yolo(self, frame: np.ndarray, frame_number: int = None) -> List[Dict[str, Any]]:
        """Run real YOLO detection"""
        detections = []
        
        # Run YOLO inference
        results = self.model(frame, verbose=False)
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Get box coordinates (xyxy format)
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                class_name = result.names[class_id]
                
                # Convert to (x, y, width, height) format
                x, y, w, h = x1, y1, x2 - x1, y2 - y1
                
                detection = {
                    'bbox': [float(x), float(y), float(w), float(h)],
                    'confidence': confidence,
                    'class_label': class_name,
                    'class_id': class_id
                }
                
                # Filter by confidence threshold
                if confidence >= self.confidence_threshold:
                    detections.append(detection)
                    
                    # Phase 5 output format
                    if frame_number is not None and class_name == 'person':
                        print(f"  Frame {frame_number} → {class_name.capitalize()} {confidence:.2f} ({int(x)}, {int(y)}, {int(w)}, {int(h)})")
        
        return detections
    
    def _detect_mock(self, frame: np.ndarray, frame_number: int = None) -> List[Dict[str, Any]]:
        """Mock detection for testing without YOLO model"""
        import math
        detections = []
        
        if frame is not None:
            # Simulate realistic detections
            height, width = frame.shape[:2]
            fn = frame_number or 0
            
            # Mock detection 1: Person walking across the screen
            # x moves by 5 pixels per frame
            x1 = 120 + (fn * 5) % max(1, (width - 80))
            detection1 = {
                'bbox': [x1, 240, 80, 180],  # (x, y, w, h)
                'confidence': 0.96,
                'class_label': 'person'
            }
            detections.append(detection1)
            
            # Mock detection 2: Person loitering (moves very little)
            # x moves slightly back and forth
            x2 = 400 + math.sin(fn * 0.1) * 10
            detection2 = {
                'bbox': [x2, 200, 75, 175],
                'confidence': 0.89,
                'class_label': 'person'
            }
            detections.append(detection2)
            
            # Phase 5 output format - Print verification
            if frame_number is not None and frame_number % 10 == 0:
                for det in detections:
                    bbox = det['bbox']
                    print(f"  Frame {frame_number} → {det['class_label'].capitalize()} {det['confidence']:.2f} ({int(bbox[0])}, {int(bbox[1])}, {int(bbox[2])}, {int(bbox[3])})")
        
        return detections
    
    def filter_persons(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter detections to only include persons
        
        Args:
            detections: List of all detections
            
        Returns:
            List of person detections only
        """
        return [d for d in detections if d['class_label'] == 'person']
    
    # ==================================================================
    # AERIX — Traffic Detection Methods
    # ==================================================================
    
    def detect_traffic(self, frame: np.ndarray, frame_number: int = None) -> List[Dict[str, Any]]:
        """
        Detect traffic-relevant objects (cars, trucks, buses, motorcycles, pedestrians, bicycles).
        
        Unlike detect() + filter_persons(), this returns ALL traffic-relevant COCO classes.
        Each detection includes a frame_number field.
        
        Args:
            frame: Image frame as numpy array
            frame_number: Frame number for logging and output
            
        Returns:
            List of detections with: bbox, confidence, class_label, class_id, frame_number
        """
        if self.use_real_yolo and self.model:
            return self._detect_traffic_real(frame, frame_number)
        else:
            return self._detect_traffic_mock(frame, frame_number)
    
    def _detect_traffic_real(self, frame: np.ndarray, frame_number: int = None) -> List[Dict[str, Any]]:
        """Run real YOLO inference, filtered to traffic-relevant COCO classes."""
        detections = []
        results = self.model(frame, verbose=False)
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                
                # Skip non-traffic classes
                if class_id not in self.TRAFFIC_COCO_IDS:
                    continue
                # Skip low confidence
                if confidence < self.confidence_threshold:
                    continue
                
                class_label = self.COCO_ID_TO_TRAFFIC[class_id]
                x, y, w, h = float(x1), float(y1), float(x2 - x1), float(y2 - y1)
                
                detections.append({
                    'bbox': [x, y, w, h],
                    'confidence': confidence,
                    'class_label': class_label,
                    'class_id': class_id,
                    'frame_number': frame_number,
                })
        
        return detections
    
    def _detect_traffic_mock(self, frame: np.ndarray, frame_number: int = None) -> List[Dict[str, Any]]:
        """Mock multi-class traffic detection for testing without a YOLO model."""
        import math
        detections = []
        
        if frame is None:
            return detections
        
        height, width = frame.shape[:2]
        fn = frame_number or 0
        
        # Car moving right across the frame
        x1 = 200 + (fn * 4) % max(1, width - 100)
        detections.append({
            'bbox': [float(x1), 300.0, 100.0, 60.0],
            'confidence': 0.93,
            'class_label': 'car',
            'class_id': 2,
            'frame_number': frame_number,
        })
        
        # Truck moving slowly
        x2 = 400 + math.sin(fn * 0.05) * 20
        detections.append({
            'bbox': [float(x2), 200.0, 140.0, 80.0],
            'confidence': 0.88,
            'class_label': 'truck',
            'class_id': 7,
            'frame_number': frame_number,
        })
        
        # Pedestrian walking
        x3 = 100 + (fn * 2) % max(1, width - 40)
        detections.append({
            'bbox': [float(x3), 400.0, 40.0, 90.0],
            'confidence': 0.91,
            'class_label': 'person',
            'class_id': 0,
            'frame_number': frame_number,
        })
        
        # Motorcycle — appears intermittently (tests occlusion handling)
        if fn % 5 < 3:
            x4 = 600 + (fn * 6) % max(1, width - 60)
            detections.append({
                'bbox': [float(x4), 350.0, 50.0, 40.0],
                'confidence': 0.85,
                'class_label': 'motorcycle',
                'class_id': 3,
                'frame_number': frame_number,
            })
        
        # Bus — stationary (tests long dwell)
        detections.append({
            'bbox': [500.0, 150.0, 160.0, 70.0],
            'confidence': 0.90,
            'class_label': 'bus',
            'class_id': 5,
            'frame_number': frame_number,
        })
        
        return detections
    
    def filter_traffic(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter detections to traffic-relevant classes only."""
        return [d for d in detections if d.get('class_id') in self.TRAFFIC_COCO_IDS]
    
    @classmethod
    def get_supported_traffic_classes(cls) -> Dict[int, str]:
        """Return the traffic classes this detector can actually distinguish.
        
        NOTE: COCO does NOT have separate LGV/HGV classes.
        The 'truck' label covers all truck types without size distinction.
        """
        return dict(cls.COCO_ID_TO_TRAFFIC)
