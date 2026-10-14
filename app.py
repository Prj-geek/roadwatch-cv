from __future__ import annotations

import threading
import uuid
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from roadwatch import AnalysisConfig, VideoAnalyzer


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


@dataclass
class Job:
    job_id: str
    status: str = "queued"
    progress: int = 0
    events: int = 0
    message: str = "Waiting to start"
    result: dict | None = None


jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()


def _update_job(job_id: str, **changes: object) -> None:
    with jobs_lock:
        job = jobs[job_id]
        for key, value in changes.items():
            setattr(job, key, value)


def _run_job(job_id: str, source: Path, config: AnalysisConfig) -> None:
    video_name = f"{job_id}-annotated.mp4"
    report_name = f"{job_id}-events.csv"

    def progress(frame: int, total: int, events: int) -> None:
        percent = min(99, int(frame / total * 100)) if total else 0
        _update_job(job_id, progress=percent, events=events, message=f"Processed {frame} frames")

    try:
        _update_job(job_id, status="running", message="Analyzing video")
        result = VideoAnalyzer(config).process(
            source, OUTPUT_DIR / video_name, OUTPUT_DIR / report_name, progress
        )
        result.update(
            {
                "video_url": f"/outputs/{video_name}",
                "report_url": f"/outputs/{report_name}",
                "config": asdict(config),
            }
        )
        _update_job(job_id, status="complete", progress=100, message="Analysis complete", result=result)
    except Exception as exc:
        _update_job(job_id, status="failed", message=str(exc))


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def analyze():
    upload = request.files.get("video")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a traffic video first."}), 400
    suffix = Path(secure_filename(upload.filename)).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Supported formats: MP4, AVI, MOV, and MKV."}), 400

    try:
        corners_value = json.loads(request.form.get("road_corners", "[]"))
        if not isinstance(corners_value, list) or len(corners_value) != 4:
            raise ValueError
        if any(
            not isinstance(point, list)
            or len(point) != 2
            or any(not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in point)
            for point in corners_value
        ):
            raise ValueError
        config = AnalysisConfig(
            speed_limit_kmh=float(request.form.get("speed_limit", 50)),
            expected_direction=request.form.get("expected_direction", "forward"),
            road_corners=tuple(tuple(point) for point in corners_value),
            road_width_m=float(request.form.get("road_width_m", 7)),
            road_length_m=float(request.form.get("road_length_m", 25)),
        )
        if config.speed_limit_kmh <= 0 or min(config.road_width_m, config.road_length_m) <= 0:
            raise ValueError
        if config.expected_direction not in {"forward", "reverse"}:
            raise ValueError
    except ValueError:
        return jsonify({"error": "One or more analysis settings are invalid."}), 400

    job_id = uuid.uuid4().hex[:12]
    source = UPLOAD_DIR / f"{job_id}{suffix}"
    upload.save(source)
    with jobs_lock:
        jobs[job_id] = Job(job_id)
    threading.Thread(target=_run_job, args=(job_id, source, config), daemon=True).start()
    return jsonify({"job_id": job_id}), 202


@app.get("/api/jobs/<job_id>")
def job_status(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify({"error": "Unknown analysis job."}), 404
        return jsonify(asdict(job))


@app.get("/outputs/<path:filename>")
def output_file(filename: str):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "The video is larger than 500 MB."}), 413


if __name__ == "__main__":
    app.run(debug=True, threaded=True)

