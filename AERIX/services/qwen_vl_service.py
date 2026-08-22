"""
Phase 15 — Qwen2.5-VL Integration

Workflow:
    Keyframe (image_path)
    ↓
    Qwen2.5-VL
    ↓
    Natural-language description

Example output:
    "A man wearing a red cap is standing near the entrance while holding a shopping bag."

Falls back to an enhanced template description when the model is not available,
so the rest of the pipeline is never blocked.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model initialisation (lazy — only attempted once)
# ---------------------------------------------------------------------------

_MODEL_LOADED: bool | None = None   # None = not attempted yet
_processor = None
_model = None


def _try_load_model() -> bool:
    """Attempt to load Qwen2.5-VL.  Returns True on success."""
    global _MODEL_LOADED, _processor, _model
    if _MODEL_LOADED is not None:
        return _MODEL_LOADED

    try:
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor  # type: ignore
        import torch  # type: ignore

        model_name = "Qwen/Qwen2.5-VL-7B-Instruct"
        logger.info("Loading Qwen2.5-VL model: %s", model_name)

        _processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
        _model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
            trust_remote_code=True,
        )
        _model.eval()
        _MODEL_LOADED = True
        logger.info("Qwen2.5-VL model loaded successfully")

    except Exception as exc:
        logger.warning("Qwen2.5-VL unavailable (%s). Using template fallback.", exc)
        _MODEL_LOADED = False

    return bool(_MODEL_LOADED)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a surveillance camera analyst. "
    "Describe the scene in a single concise sentence. "
    "Focus on: person appearance (clothing, colours, accessories), "
    "action (walking, stopped, picking up, running), "
    "and location context if visible. "
    "Do NOT speculate. If something is not visible, omit it."
)

_EVENT_HINTS: dict[str, str] = {
    "person_entered_scene":  "A person just entered the camera view.",
    "person_exited_scene":   "A person is leaving the camera view.",
    "stopped_moving":        "A person has stopped moving.",
    "running":               "A person appears to be running.",
    "direction_changed":     "A person changed direction.",
    "loitering":             "A person has been stationary for an extended period.",
    "object_picked":         "A person appears to be picking up an object.",
    "person_near_object":    "A person is close to an object of interest.",
    "entered_zone":          "A person has entered a monitored zone.",
    "exited_zone":           "A person has exited a monitored zone.",
    "object_abandoned":      "An object may have been left unattended.",
    "person_disappeared":    "A person has disappeared from view.",
    "crowd_formed":          "A group of people has gathered.",
    "fall_detected":         "A person may have fallen.",
}


def _build_user_prompt(event_type: str, metadata: dict[str, Any] | None) -> str:
    hint = _EVENT_HINTS.get(event_type, "")
    hint_text = f" Context: {hint}" if hint else ""
    objects = (metadata or {}).get("objects")
    objects_text = f" Visible objects: {', '.join(objects)}." if objects else ""
    return (
        f"Describe the person and activity in this surveillance frame.{hint_text}{objects_text}"
    )


# ---------------------------------------------------------------------------
# Fallback template (when Qwen2.5-VL is not available)
# ---------------------------------------------------------------------------

def _template_description(
    event_type: str,
    metadata: dict[str, Any] | None,
) -> str:
    """Rich template descriptions — used when model is unavailable."""
    objects = (metadata or {}).get("objects") or []
    object_phrase = f", carrying {', '.join(objects)}" if objects else ""
    speed = (metadata or {}).get("speed")
    speed_phrase = f" (speed ≈ {speed:.1f} px/frame)" if speed else ""

    templates: dict[str, str] = {
        "person_entered_scene":  f"A person entered the camera view{object_phrase}.",
        "person_exited_scene":   f"A person exited the camera view{object_phrase}.",
        "started_walking":       f"A person began walking{object_phrase}{speed_phrase}.",
        "stopped_moving":        f"A person stopped and is standing still{object_phrase}.",
        "running":               f"A person is running through the frame{object_phrase}{speed_phrase}.",
        "direction_changed":     f"A person changed direction while moving{object_phrase}.",
        "loitering":             f"A person has been standing in the same area for an extended time{object_phrase}.",
        "object_picked":         "A person bent down and picked up an object.",
        "person_near_object":    "A person is standing close to an object of interest.",
        "entered_zone":          "A person entered a monitored area.",
        "exited_zone":           "A person left a monitored area.",
        "object_abandoned":      "An object appears to have been left unattended in the frame.",
        "person_disappeared":    "A person has disappeared from the camera view.",
        "crowd_formed":          "Multiple people have gathered together in the frame.",
        "fall_detected":         "A person appears to have fallen to the ground.",
        "person_left_object":    "A person placed or left an object and moved away.",
        "person_picked_object":  "A person picked up an object from the area.",
    }
    return templates.get(event_type, f"A person is visible in the frame ({event_type.replace('_', ' ')}).")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def describe_keyframe(
    image_path: str | Path,
    event_type: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[str, float, bool]:
    """
    Generate a natural-language description for a keyframe.

    Returns:
        (description, confidence, used_vlm)
            description  — human-readable sentence
            confidence   — 0.0–1.0
            used_vlm     — True if Qwen2.5-VL was used
    """
    image_path = Path(image_path)

    if not image_path.exists():
        logger.warning("Keyframe image not found: %s", image_path)
        return _template_description(event_type, metadata), 0.0, False

    if _try_load_model():
        try:
            return _run_qwen_inference(image_path, event_type, metadata)
        except Exception as exc:
            logger.error("Qwen2.5-VL inference failed: %s", exc)

    # Graceful fallback
    return _template_description(event_type, metadata), 0.5, False


def _run_qwen_inference(
    image_path: Path,
    event_type: str,
    metadata: dict[str, Any] | None,
) -> tuple[str, float, bool]:
    """Run actual Qwen2.5-VL inference."""
    from PIL import Image  # type: ignore
    import torch  # type: ignore
    from qwen_vl_utils import process_vision_info  # type: ignore

    image = Image.open(image_path).convert("RGB")
    user_prompt = _build_user_prompt(event_type, metadata)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text",  "text": user_prompt},
            ],
        }
    ]

    text = _processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        system_message=_SYSTEM_PROMPT,
    )
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = _processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(_model.device)

    with torch.no_grad():
        generated_ids = _model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=False,
        )

    # Decode only the generated tokens
    generated_ids_trimmed = [
        out_ids[len(in_ids):]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = _processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()

    logger.debug("Qwen2.5-VL description: %s", output_text)
    return output_text, 0.92, True
