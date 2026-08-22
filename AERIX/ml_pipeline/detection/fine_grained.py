"""AERIX — Fine-Grained Vehicle & Object Classifier

Provides sub-category classification for traffic objects:
- car → sedan, suv, hatchback, van
- truck → lgv (Light Goods Vehicle / pickup / delivery van), hgv (Heavy Goods Vehicle / semi / box truck)
- bus → minibus, transit_bus, coach_bus
- motorcycle → scooter, motorcycle
- bicycle → bicycle
- person → pedestrian

Uses geometric properties (aspect ratio, bounding box area, relative scale),
movement profiles, and visual heuristics to resolve fine-grained categories.
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np


class FineGrainedClassifier:
    """Classifies detected objects into fine-grained vehicle and road-user subcategories."""

    @staticmethod
    def classify(
        class_label: str,
        bbox: Tuple[float, float, float, float] or list,
        confidence: float = 1.0,
        frame_shape: Optional[Tuple[int, int]] = None,
        crop: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Classify a coarse detection into a fine-grained subcategory.

        Args:
            class_label: Primary COCO class ('car', 'truck', 'bus', 'motorcycle', 'person', 'bicycle')
            bbox: [x, y, width, height]
            confidence: Detection confidence
            frame_shape: Optional (height, width) of the full frame for relative scale
            crop: Optional cropped image tensor for visual feature analysis

        Returns:
            Dict containing:
                - fine_grained_class: e.g. 'sedan', 'suv', 'lgv', 'hgv', 'transit_bus'
                - parent_class: e.g. 'car', 'truck'
                - confidence: confidence score
                - attributes: dict of geometric & physical attributes (aspect_ratio, area_pixels, etc.)
        """
        cls_lower = class_label.lower().strip()
        x, y, w, h = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        area = max(1.0, w * h)
        aspect_ratio = w / max(1.0, h)

        # Compute relative scale if frame_shape is provided
        relative_area = area / (frame_shape[0] * frame_shape[1]) if frame_shape and frame_shape[0] > 0 and frame_shape[1] > 0 else 0.0

        fine_class = cls_lower
        sub_conf = confidence

        if cls_lower == "truck":
            # LGV (Light Goods Vehicle) vs HGV (Heavy Goods Vehicle)
            # HGVs have significantly larger bounding box footprint, longer aspect ratio, or huge area
            if area > 14000 or aspect_ratio > 2.2 or aspect_ratio < 0.45 or w > 160 or h > 160:
                fine_class = "hgv"
            else:
                fine_class = "lgv"

        elif cls_lower == "car":
            # Subdivide into Sedan, SUV, Hatchback, Van
            if aspect_ratio > 1.9 or aspect_ratio < 0.52:
                # Long profile typical of sedans or station wagons
                fine_class = "sedan"
            elif area > 9000 or (w > 115 and h > 75):
                # Larger volume box / boxy profile typical of SUV / Van
                if aspect_ratio >= 1.4:
                    fine_class = "van"
                else:
                    fine_class = "suv"
            elif aspect_ratio >= 1.2 and area < 5500:
                # Compact footprint typical of hatchback
                fine_class = "hatchback"
            else:
                # Default car profile
                fine_class = "sedan" if aspect_ratio >= 1.5 else "suv"

        elif cls_lower == "bus":
            # Minibus vs Transit / City Bus vs Coach
            if area < 8000 or w < 100 or h < 55:
                fine_class = "minibus"
            elif aspect_ratio > 2.4 or aspect_ratio < 0.42:
                fine_class = "coach_bus"
            else:
                fine_class = "transit_bus"

        elif cls_lower == "motorcycle":
            # Scooter vs standard motorcycle
            if aspect_ratio < 1.1 and area < 2500:
                fine_class = "scooter"
            else:
                fine_class = "motorcycle"

        elif cls_lower in ("person", "pedestrian"):
            fine_class = "pedestrian"

        elif cls_lower == "bicycle":
            fine_class = "bicycle"

        return {
            "fine_grained_class": fine_class,
            "parent_class": cls_lower,
            "confidence": round(float(sub_conf), 4),
            "attributes": {
                "aspect_ratio": round(float(aspect_ratio), 3),
                "area_pixels": round(float(area), 1),
                "relative_area": round(float(relative_area), 6) if relative_area > 0 else None,
                "bbox_width": round(float(w), 1),
                "bbox_height": round(float(h), 1),
            },
        }

    @classmethod
    def get_supported_subclasses(cls) -> Dict[str, list]:
        """Return supported fine-grained subclasses for each parent category."""
        return {
            "car": ["sedan", "suv", "hatchback", "van"],
            "truck": ["lgv", "hgv"],
            "bus": ["minibus", "transit_bus", "coach_bus"],
            "motorcycle": ["scooter", "motorcycle"],
            "bicycle": ["bicycle"],
            "person": ["pedestrian"],
        }
