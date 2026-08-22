"""
AERIX — Traffic Detection & Tracking Pipeline
Level 1: Detect and track every road user with stable identity.
Object-Level Insight: Fine-grained classification & Real-unit Kinematics (speed & acceleration).

Standalone entry point — no database required.

Usage:
    python -m ml_pipeline.traffic_pipeline --video path/to/drone_video.mp4

Pipeline:
    Video → Frame Sampler → YOLO detect_traffic → ByteTrack → Track Manager (Fine-Grained & Kinematics) → Annotated MP4
"""

import cv2
import json
import time
import math
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List

import numpy as np

from ml_pipeline.ingestion.video_loader import VideoLoader
from ml_pipeline.ingestion.frame_sampler import FrameSampler
from ml_pipeline.detection.yolo_detector import YOLODetector
from ml_pipeline.tracking.bytetrack import ByteTrackTracker
from ml_pipeline.tracking.track_manager import TrackManager

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AERIX] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aerix")

# ── Annotation colours (BGR) ────────────────────────────────────────
CLASS_COLORS = {
    'person':     (0, 220, 0),       # green
    'pedestrian': (0, 220, 0),       # green
    'car':        (255, 144, 30),     # dodger-blue
    'sedan':      (255, 144, 30),     # blue
    'suv':        (255, 180, 50),     # light blue
    'hatchback':  (230, 120, 20),     # dark blue
    'van':        (200, 160, 40),     # slate
    'motorcycle': (0, 255, 255),      # yellow
    'scooter':    (50, 205, 255),     # light yellow
    'bus':        (0, 165, 255),      # orange
    'minibus':    (30, 180, 255),     # light orange
    'transit_bus':(0, 140, 255),      # deep orange
    'coach_bus':  (0, 120, 230),      # amber
    'truck':      (0, 0, 255),        # red
    'lgv':        (50, 50, 255),      # light red
    'hgv':        (0, 0, 200),        # dark red
    'bicycle':    (255, 0, 255),      # magenta
}
DEFAULT_COLOR = (200, 200, 200)


# ── Core pipeline ────────────────────────────────────────────────────

def process_traffic_video(
    video_path: str,
    output_path: Optional[str] = None,
    sample_rate: int = 3,
    confidence_threshold: float = 0.3,
    model: str = "yolov8s.pt",
    use_real_yolo: bool = True,
    draw_trails: bool = True,
    draw_vectors: bool = True,
    trail_length: int = 30,
    pixels_per_meter: float = 15.0,
    progress_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    """Process a traffic video through the AERIX pipeline with fine-grained classification & kinematics.

    Args:
        video_path: Path to input video file
        output_path: Path for annotated output video (default: <input>_tracked.mp4)
        sample_rate: Process every Nth frame (default: 3 → ~10 fps from 30 fps)
        confidence_threshold: Min detection confidence (default: 0.3)
        model: YOLO model name/path (default: yolov8s.pt)
        use_real_yolo: True for real YOLO, False for mock (testing)
        draw_trails: Whether to draw trajectory trails behind objects
        draw_vectors: Whether to draw velocity vectors on objects
        trail_length: Number of recent points for trajectory trail
        pixels_per_meter: Pixel to real-world meter conversion scale
        progress_callback: Optional callback for streaming progress updates

    Returns:
        Summary dict with processing statistics, kinematics, and fine-grained classification
    """
    start_time = time.time()

    # ── Resolve paths ────────────────────────────────────────────────
    video_path = str(Path(video_path).resolve())
    if output_path is None:
        p = Path(video_path)
        output_path = str(p.parent / f"{p.stem}_tracked.mp4")
    output_path = str(Path(output_path).resolve())

    logger.info("=" * 60)
    logger.info("AERIX — Traffic Detection, Tracking & Kinematics")
    logger.info("=" * 60)
    logger.info("Input  : %s", video_path)
    logger.info("Output : %s", output_path)
    logger.info("Model  : %s (real=%s)", model, use_real_yolo)
    logger.info("Sample : every %d frames", sample_rate)
    logger.info("Conf   : %.2f", confidence_threshold)
    logger.info("Scale  : %.2f px/m", pixels_per_meter)

    # ── Initialise components ────────────────────────────────────────
    try:
        loader = VideoLoader(video_path)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Cannot open video: %s", exc)
        return _error_result(video_path, str(exc))

    logger.info("VIDEO  : %d frames, %d fps, %dx%d",
                loader.total_frames, loader.fps, loader.width, loader.height)

    sampler = FrameSampler(sample_rate=sample_rate)

    detector = YOLODetector(
        model_path=model,
        confidence_threshold=confidence_threshold,
        use_real_yolo=use_real_yolo,
    )

    effective_fps = max(1, loader.fps // sample_rate)
    tracker = ByteTrackTracker(
        track_activation_threshold=0.25,
        lost_track_buffer=30,
        minimum_matching_threshold=0.8,
        frame_rate=effective_fps,
    )

    track_manager = TrackManager(
        pixels_per_meter=pixels_per_meter,
        sample_rate=sample_rate,
    )

    # ── Video writer ─────────────────────────────────────────────────
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(
        output_path, fourcc, effective_fps,
        (loader.width, loader.height),
    )
    if not writer.isOpened():
        logger.error("Cannot create output video writer at: %s", output_path)
        loader.release()
        return _error_result(video_path, "Failed to create output video writer")

    # ── Processing loop ──────────────────────────────────────────────
    total_detections = 0
    frames_processed = 0
    detection_errors = 0

    logger.info("PROCESS START")

    try:
        for frame_number, frame in sampler.sample(loader.get_frames()):
            frames_processed += 1

            # ── Detect ───────────────────────────────────────────────
            try:
                detections = detector.detect_traffic(frame, frame_number)
            except Exception as det_exc:
                detection_errors += 1
                logger.warning("Detection error on frame %d: %s", frame_number, det_exc)
                detections = []

            total_detections += len(detections)

            # ── Track ────────────────────────────────────────────────
            tracked_objects, lifecycle = tracker.update(detections, frame_number)

            # ── Update track history & kinematics ────────────────────
            track_manager.update(
                tracked_objects,
                frame_number,
                loader.fps,
                frame_shape=(loader.height, loader.width),
            )
            track_manager.mark_lost(lifecycle.get('lost', []))

            # ── Annotate & write ─────────────────────────────────────
            annotated = _annotate_frame(
                frame, tracked_objects, track_manager,
                draw_trails=draw_trails,
                draw_vectors=draw_vectors,
                trail_length=trail_length,
            )
            writer.write(annotated)

            # ── Progress logging & callback ──────────────────────────
            if frames_processed % 30 == 0 or frames_processed == 1:
                pct = round((frame_number / max(1, loader.total_frames)) * 100, 1)
                all_sums = track_manager.get_all_summaries()
                class_counts = track_manager.get_class_counts()
                fine_counts = track_manager.get_fine_grained_class_counts()
                kin_summary = track_manager.get_kinematics_summary()

                if progress_callback:
                    try:
                        progress_callback({
                            "status": "processing",
                            "progress": pct,
                            "frames_processed": frames_processed,
                            "total_frames": loader.total_frames,
                            "detections": total_detections,
                            "unique_tracks": len(all_sums),
                            "class_counts": class_counts,
                            "fine_grained_class_counts": fine_counts,
                            "kinematics": kin_summary,
                            "active_tracks": len(tracker.active_tracks),
                        })
                    except Exception:
                        pass

                if frames_processed % 90 == 0 or frames_processed == 1:
                    logger.info(
                        "FRAME %d (%.0f%%) | %d dets | %d active | %d total | Avg Spd: %.1f km/h",
                        frame_number, pct, len(detections),
                        len(tracker.active_tracks), len(track_manager),
                        kin_summary.get("average_speed_kmh", 0.0),
                    )

    except Exception as proc_exc:
        logger.error("Processing error at frame %d: %s", frame_number, proc_exc)
        import traceback
        traceback.print_exc()
    finally:
        writer.release()
        loader.release()

    # ── Summary ──────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    all_summaries = track_manager.get_all_summaries()
    class_counts = track_manager.get_class_counts()
    fine_counts = track_manager.get_fine_grained_class_counts()
    kinematics_summary = track_manager.get_kinematics_summary()

    # Calculate overall average confidence across all tracked instances
    all_confs = [
        conf
        for summary in all_summaries
        for conf in summary.get("confidence_history", [])
    ]
    avg_conf = round(float(np.mean(all_confs)), 4) if all_confs else 0.0

    result = {
        "video_id": Path(video_path).stem,
        "status": "completed",
        "frames_processed": frames_processed,
        "detections": total_detections,
        "detection_errors": detection_errors,
        "unique_tracks": len(all_summaries),
        "classes_detected": sorted(class_counts.keys()),
        "class_counts": class_counts,
        "fine_grained_class_counts": fine_counts,
        "kinematics_summary": kinematics_summary,
        "pixels_per_meter": pixels_per_meter,
        "average_confidence": avg_conf,
        "output_video": output_path,
        "processing_time": round(elapsed, 2),
        "processing_time_seconds": round(elapsed, 2),
        "effective_fps_processed": round(frames_processed / max(elapsed, 0.01), 1),
        "tracker_config": tracker.get_config(),
        "model": model,
        "sample_rate": sample_rate,
        "confidence_threshold": confidence_threshold,
        "tracks": all_summaries,
    }

    logger.info("=" * 60)
    logger.info("PROCESS COMPLETE")
    logger.info("  Frames processed : %d", frames_processed)
    logger.info("  Total detections : %d", total_detections)
    logger.info("  Unique tracks    : %d", len(all_summaries))
    logger.info("  Classes          : %s", class_counts)
    logger.info("  Fine-Grained     : %s", fine_counts)
    logger.info("  Avg Fleet Speed  : %.1f km/h | Max Speed: %.1f km/h",
                kinematics_summary["average_speed_kmh"], kinematics_summary["max_speed_kmh"])
    logger.info("  Processing time  : %.1fs", elapsed)
    logger.info("  Output video     : %s", output_path)
    logger.info("=" * 60)

    return result


# ── Annotation helpers ───────────────────────────────────────────────

def _annotate_frame(
    frame: np.ndarray,
    tracked_objects: List[Dict[str, Any]],
    track_manager: TrackManager,
    draw_trails: bool = True,
    draw_vectors: bool = True,
    trail_length: int = 30,
) -> np.ndarray:
    """Draw bounding boxes, fine-grained labels, track IDs, kinematics (km/h & m/s²), and trajectory trails."""
    annotated = frame.copy()

    for obj in tracked_objects:
        x, y, w, h = [int(v) for v in obj['bbox']]
        track_id = obj['track_id']
        fg_cls = obj.get('fine_grained_class', obj['class_label']).upper()
        conf = obj.get('confidence', 0.0)
        color = CLASS_COLORS.get(obj.get('fine_grained_class', obj['class_label']), DEFAULT_COLOR)

        kin = obj.get('kinematics', {})
        speed_kmh = kin.get('current_speed_kmh', 0.0)
        accel_ms2 = kin.get('current_acceleration_ms2', 0.0)
        direction = kin.get('cardinal_direction', '')
        status = kin.get('motion_status', 'Cruising')

        # Bounding box
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

        # Top Label: FG_CLASS #ID CONF
        top_label = f"{fg_cls} #{track_id}"
        (tw, th), _ = cv2.getTextSize(top_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(annotated, (x, y - th - 8), (x + tw + 6, y), color, -1)
        cv2.putText(
            annotated, top_label, (x + 3, y - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2,
        )

        # Bottom Kinematics Tag: SPEED km/h | ACCEL m/s² [DIR]
        accel_sign = "+" if accel_ms2 >= 0 else ""
        kin_label = f"{speed_kmh:.1f} km/h | {accel_sign}{accel_ms2:.1f}m/s2 {direction}"
        (kw, kh), _ = cv2.getTextSize(kin_label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        
        # Tag background
        cv2.rectangle(annotated, (x, y + h), (x + kw + 6, y + h + kh + 6), (20, 20, 20), -1)
        cv2.rectangle(annotated, (x, y + h), (x + kw + 6, y + h + kh + 6), color, 1)
        cv2.putText(
            annotated, kin_label, (x + 3, y + h + kh + 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (240, 240, 240), 1,
        )

        # Trajectory trail
        if draw_trails:
            points = track_manager.get_trajectory_points(track_id, last_n=trail_length)
            if len(points) > 1:
                for i in range(1, len(points)):
                    alpha = i / len(points)
                    thickness = max(1, int(alpha * 3))
                    cv2.line(annotated, points[i - 1], points[i], color, thickness)

        # Velocity Vector Arrow
        if draw_vectors and 'velocity_vector_ms' in kin:
            vx, vy = kin['velocity_vector_ms']
            if abs(vx) > 0.1 or abs(vy) > 0.1:
                cx = int(x + w / 2)
                cy = int(y + h / 2)
                # Scale velocity vector for visual arrow length
                end_x = int(cx + vx * 6.0)
                end_y = int(cy + vy * 6.0)
                cv2.arrowedLine(annotated, (cx, cy), (end_x, end_y), (0, 255, 255), 2, tipLength=0.3)

    # Frame info HUD overlay (Top-Left Glassmorphic Box)
    kin_summary = track_manager.get_kinematics_summary()
    info_title = f"AERIX OBJECT INTELLIGENCE | Active: {len(tracked_objects)} | Fleet: {len(track_manager)}"
    info_speed = f"Avg Speed: {kin_summary['average_speed_kmh']:.1f} km/h | Max: {kin_summary['max_speed_kmh']:.1f} km/h"

    cv2.rectangle(annotated, (8, 8), (460, 68), (15, 23, 42), -1)
    cv2.rectangle(annotated, (8, 8), (460, 68), (59, 130, 246), 1)

    cv2.putText(annotated, info_title, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2)
    cv2.putText(annotated, info_speed, (16, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (56, 189, 248), 1)

    return annotated


def _error_result(video_path: str, reason: str) -> Dict[str, Any]:
    """Build an error result dict."""
    return {
        "video_id": Path(video_path).stem,
        "status": "failed",
        "reason": reason,
        "frames_processed": 0,
        "detections": 0,
        "unique_tracks": 0,
        "classes_detected": [],
        "fine_grained_class_counts": {},
        "kinematics_summary": {},
        "output_video": None,
    }


# ── CLI entry point ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AERIX — Traffic Detection, Tracking & Kinematics",
    )
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument("--output", default=None, help="Path for annotated output video")
    parser.add_argument("--sample-rate", type=int, default=3,
                        help="Process every Nth frame (default: 3)")
    parser.add_argument("--confidence", type=float, default=0.3,
                        help="Min detection confidence (default: 0.3)")
    parser.add_argument("--pixels-per-meter", type=float, default=15.0,
                        help="Pixel to meter calibration factor (default: 15.0)")
    parser.add_argument("--model", default="yolov8s.pt",
                        help="YOLO model (default: yolov8s.pt)")
    parser.add_argument("--mock", action="store_true",
                        help="Use mock detector (no GPU needed)")
    parser.add_argument("--no-trails", action="store_true",
                        help="Disable trajectory trails")
    parser.add_argument("--no-vectors", action="store_true",
                        help="Disable velocity vector arrows")
    parser.add_argument("--json-output", default=None,
                        help="Optional path to save results summary JSON")
    args = parser.parse_args()

    result = process_traffic_video(
        video_path=args.video,
        output_path=args.output,
        sample_rate=args.sample_rate,
        confidence_threshold=args.confidence,
        model=args.model,
        use_real_yolo=not args.mock,
        draw_trails=not args.no_trails,
        draw_vectors=not args.no_vectors,
        pixels_per_meter=args.pixels_per_meter,
    )

    if args.json_output:
        json_path = Path(args.json_output).resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info("Saved results JSON to: %s", str(json_path))

    print("\n" + json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
