"""
Generate a realistic sample drone traffic video with moving cars, trucks, buses, motorcycles, pedestrians,
and run the AERIX Level 1 pipeline on it to produce high-quality annotated demonstration output.
"""
import os
import cv2
import numpy as np
from ml_pipeline.traffic_pipeline import process_traffic_video

def generate_sample_drone_video(output_path="storage/uploads/sample_drone_traffic.mp4", duration_sec=15, fps=30):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    width, height = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = duration_sec * fps
    print(f"Generating {total_frames} frames of simulated aerial drone traffic...")

    for i in range(total_frames):
        # Aerial asphalt intersection background
        frame = np.full((height, width, 3), (45, 52, 54), dtype=np.uint8)

        # Crossroad asphalt & road markings
        cv2.rectangle(frame, (0, 240), (1280, 480), (35, 40, 42), -1)  # Horizontal road
        cv2.rectangle(frame, (480, 0), (800, 720), (35, 40, 42), -1)   # Vertical road
        
        # Lane divider lines (dashed)
        for x in range(0, 1280, 40):
            cv2.line(frame, (x, 360), (x + 20, 360), (255, 255, 255), 2)
        for y in range(0, 720, 40):
            cv2.line(frame, (640, y), (640, y + 20), (255, 255, 255), 2)

        # Draw vehicle 1: Car moving Left to Right
        x1 = int((i * 6) % 1350) - 100
        cv2.rectangle(frame, (x1, 280), (x1 + 90, 330), (230, 120, 30), -1)
        cv2.putText(frame, "CAR", (x1 + 10, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Draw vehicle 2: Truck moving Top to Bottom (slow)
        y2 = int((i * 3) % 850) - 120
        cv2.rectangle(frame, (520, y2), (580, y2 + 130), (40, 60, 200), -1)
        cv2.putText(frame, "TRUCK", (525, y2 + 65), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Draw vehicle 3: Bus stationary at bus stop (long dwell time)
        cv2.rectangle(frame, (900, 400), (1060, 460), (30, 160, 240), -1)
        cv2.putText(frame, "BUS", (920, 435), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        # Draw vehicle 4: Motorcycle moving Right to Left (fast)
        x4 = int(1300 - ((i * 10) % 1400))
        cv2.rectangle(frame, (x4, 400), (x4 + 45, 430), (0, 220, 220), -1)

        # Draw pedestrian crossing
        yp = int(220 + (i * 1.5) % 280)
        cv2.circle(frame, (450, yp), 12, (50, 200, 50), -1)

        out.write(frame)

    out.release()
    print(f"Sample video generated: {output_path}")
    return output_path

if __name__ == "__main__":
    video_path = generate_sample_drone_video()
    print("Processing sample video through AERIX Level 1...")
    res = process_traffic_video(
        video_path=video_path,
        output_path="storage/videos/level1_output.mp4",
        sample_rate=3,
        confidence_threshold=0.3,
        use_real_yolo=False,
    )
    import json
    with open("level1_results.json", "w") as f:
        json.dump(res, f, indent=2, default=str)
    print("Level 1 sample demonstration generated successfully!")
