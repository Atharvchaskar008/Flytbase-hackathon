from datetime import datetime
from typing import Any, List
from sqlalchemy.orm import Session

from database.models.keyframe import Keyframe
from database.repository.description_repository import create_description
from services.qwen_vl_service import describe_keyframe


class DescriptionService:
    """Service for generating and storing keyframe descriptions.

    Phase 15: Uses Qwen2.5-VL to generate rich natural-language descriptions
    from the saved keyframe image.  Falls back to templates automatically if
    the model is unavailable.
    """

    def generate_description_text(
        self,
        keyframe: Keyframe,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, float]:
        """Generate a human-readable description for a keyframe.

        Returns (description_text, confidence).
        If the keyframe has a saved image, Qwen2.5-VL is attempted first.
        """
        if keyframe.image_path:
            description, confidence, used_vlm = describe_keyframe(
                image_path=keyframe.image_path,
                event_type=event_type,
                metadata=metadata,
            )
            return description, confidence

        # No image on disk — use the template fallback directly
        from services.qwen_vl_service import _template_description
        return _template_description(event_type, metadata), 0.5

    def create_description_for_keyframe(
        self,
        db: Session,
        keyframe: Keyframe,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ):
        description_text, confidence = self.generate_description_text(keyframe, event_type, metadata)
        objects = metadata.get('objects') if metadata else []
        # Use Qwen confidence if provided; fall back to detection confidence
        if confidence == 0.5 and metadata:
            confidence = float(metadata.get('confidence', 0.5))

        return create_description(
            db=db,
            track_id=keyframe.track_id,
            keyframe_id=keyframe.id,
            video_id=keyframe.video_id,
            frame_number=keyframe.frame_number,
            timestamp=keyframe.timestamp,
            description=description_text,
            objects=objects or [],
            confidence=confidence,
            metadata=metadata,
        )
