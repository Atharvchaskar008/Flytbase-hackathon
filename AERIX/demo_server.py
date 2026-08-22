"""
AERIX Demo Server — Lightweight standalone server for Level 1 demo.
Serves the frontend HTML, the processed video, and results JSON.
No database required. No React build required.

Usage:
    python demo_server.py
    Open http://localhost:8080
"""

import json
import shutil
import uuid
import os
import time
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

PROJECT_ROOT = Path(__file__).parent.resolve()
STORAGE_DIR = PROJECT_ROOT / "storage"
VIDEOS_DIR = STORAGE_DIR / "videos"
UPLOADS_DIR = STORAGE_DIR / "uploads"
RESULTS_FILE = PROJECT_ROOT / "level1_results.json"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Track processing state
processing_state = {
    "status": "idle",
    "progress": 0,
    "result": None,
}


class AERIXHandler(SimpleHTTPRequestHandler):
    """Custom handler for the AERIX demo."""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._serve_file(PROJECT_ROOT / "demo_frontend.html", "text/html")
        elif path == "/api/results":
            self._serve_json_results()
        elif path == "/api/status":
            self._serve_json(processing_state)
        elif path.startswith("/videos/"):
            video_name = path[len("/videos/"):]
            video_path = VIDEOS_DIR / video_name
            if video_path.exists():
                self._serve_file(video_path, "video/mp4")
            else:
                self.send_error(404, f"Video not found: {video_name}")
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/upload":
            self._handle_upload()
        elif path == "/api/process":
            self._handle_process()
        else:
            self.send_error(404, "Not found")

    def _serve_file(self, filepath, content_type):
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404, "File not found")

    def _serve_json(self, obj):
        data = json.dumps(obj, indent=2, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_json_results(self):
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, "r") as f:
                results = json.load(f)
            # Fix the output video URL for the frontend
            results["output_video_url"] = "/videos/level1_output.mp4"
            self._serve_json(results)
        else:
            self._serve_json({"status": "no_results", "message": "No processing results yet."})

    def _handle_upload(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_error(400, "No file uploaded")
            return

        # Read multipart boundary
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            # Simple binary upload
            body = self.rfile.read(content_length)
            filename = f"upload_{uuid.uuid4().hex[:8]}.mp4"
            save_path = UPLOADS_DIR / filename
            with open(save_path, "wb") as f:
                f.write(body)
            self._serve_json({"status": "uploaded", "filename": filename, "path": str(save_path)})
            return

        # For multipart, read the whole body and extract the file
        body = self.rfile.read(content_length)
        boundary = content_type.split("boundary=")[1].encode()

        parts = body.split(b"--" + boundary)
        for part in parts:
            if b"filename=" in part:
                # Extract filename
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                file_data = part[header_end + 4:]
                if file_data.endswith(b"\r\n"):
                    file_data = file_data[:-2]

                filename = f"upload_{uuid.uuid4().hex[:8]}.mp4"
                save_path = UPLOADS_DIR / filename
                with open(save_path, "wb") as f:
                    f.write(file_data)

                self._serve_json({"status": "uploaded", "filename": filename, "path": str(save_path)})
                return

        self.send_error(400, "No file found in upload")

    def _handle_process(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}

        video_path = params.get("video_path", "")

        if not video_path or not Path(video_path).exists():
            # Try using the recording in parent directory
            recording = PROJECT_ROOT.parent / "Recording 2026-08-22 122728.mp4"
            if recording.exists():
                video_path = str(recording)
            else:
                self.send_error(400, "No video file found to process")
                return

        processing_state["status"] = "processing"
        processing_state["progress"] = 0

        def on_progress(data):
            processing_state.update(data)

        def run_pipeline():
            try:
                from ml_pipeline.traffic_pipeline import process_traffic_video
                result = process_traffic_video(
                    video_path=video_path,
                    output_path=str(VIDEOS_DIR / "level1_output.mp4"),
                    sample_rate=3,
                    confidence_threshold=0.3,
                    model="yolov8n.pt",
                    use_real_yolo=True,
                    progress_callback=on_progress,
                )
                # Save results
                with open(RESULTS_FILE, "w") as f:
                    json.dump(result, f, indent=2, default=str)
                processing_state["status"] = "completed"
                processing_state["progress"] = 100
                processing_state["result"] = result
            except Exception as e:
                processing_state["status"] = "error"
                processing_state["result"] = {"error": str(e)}

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        self._serve_json({"status": "processing", "message": "Pipeline started in background"})

    def log_message(self, format, *args):
        # Quieter logging
        if "/api/" in str(args[0]) or args[0] == '"GET / HTTP/1.1"':
            pass  # suppress noisy requests
        else:
            super().log_message(format, *args)


def main():
    port = 8888
    server = HTTPServer(("0.0.0.0", port), AERIXHandler)
    print("=" * 60)
    print("AERIX — Level 1 Demo Server")
    print("=" * 60)
    print(f"  Open: http://localhost:{port}")
    print(f"  Video: {VIDEOS_DIR / 'level1_output.mp4'}")
    print(f"  Results: {RESULTS_FILE}")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
