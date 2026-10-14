"""YOLO + ByteTrack video analysis with road-plane speed calibration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from ultralytics import YOLO

from .rules import VehicleTrack, Violation, estimate_speed_kmh, evaluate_track
from .reporting import confirmed_vehicles, write_csv_report


@dataclass(frozen=True)
class AnalysisConfig:
    speed_limit_kmh: float = 50.0
    expected_direction: str = "forward"
    road_corners: tuple[tuple[float, float], ...] = ()
    road_width_m: float = 7.0
    road_length_m: float = 25.0
    confidence: float = 0.3
    minimum_track_age_s: float = 1.0
    max_plausible_speed_kmh: float = 160.0
    persistence_frames: int = 15
    model_name: str = "yolo11n.pt"
    image_size: int = 960


class VideoAnalyzer:
    def __init__(self, config: AnalysisConfig) -> None:
        self.config = config
        self.model = YOLO(config.model_name)

    @staticmethod
    def _road_homography(
        corners: tuple[tuple[float, float], ...],
        frame_width: int,
        frame_height: int,
        road_width_m: float,
        road_length_m: float,
    ) -> np.ndarray:
        if len(corners) != 4:
            raise ValueError("Mark all four road boundary corners before running speed analysis.")
        source = np.asarray(
            [[x * frame_width, y * frame_height] for x, y in corners],
            dtype=np.float32,
        )
        contour = source.reshape((-1, 1, 2))
        if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < frame_width * frame_height * 0.005:
            raise ValueError("Calibration points must outline a visible road quadrilateral in corner order.")
        if min(road_width_m, road_length_m) <= 0:
            raise ValueError("Road width and calibration length must be greater than zero.")
        destination = np.asarray(
            [[0, 0], [road_width_m, 0], [road_width_m, road_length_m], [0, road_length_m]],
            dtype=np.float32,
        )
        return cv2.getPerspectiveTransform(source, destination)

    @staticmethod
    def _world_position(
        homography: np.ndarray,
        box: tuple[int, int, int, int],
    ) -> tuple[float, float]:
        x1, y1, x2, y2 = box
        foot = np.asarray([[[((x1 + x2) / 2.0), y2]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(foot, homography)[0, 0]
        return float(transformed[0]), float(transformed[1])

    @staticmethod
    def _draw_calibration(frame: np.ndarray, corners: tuple[tuple[float, float], ...]) -> None:
        height, width = frame.shape[:2]
        points = np.asarray(
            [[int(x * width), int(y * height)] for x, y in corners], dtype=np.int32
        )
        cv2.polylines(frame, [points.reshape((-1, 1, 2))], True, (40, 230, 255), 2)

    def process(
        self,
        source: Path,
        output_video: Path,
        output_csv: Path,
        progress: Callable[[int, int, int], None] | None = None,
    ) -> dict[str, float | int]:
        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            raise ValueError("The uploaded file could not be opened as a video.")

        fps = capture.get(cv2.CAP_PROP_FPS)
        if not np.isfinite(fps) or fps <= 0:
            capture.release()
            raise ValueError("Could not read a valid frame rate from this video.")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        try:
            homography = self._road_homography(
                self.config.road_corners,
                width,
                height,
                self.config.road_width_m,
                self.config.road_length_m,
            )
        except Exception:
            capture.release()
            raise

        writer = cv2.VideoWriter(
            str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
        if not writer.isOpened():
            capture.release()
            raise RuntimeError("Could not create the annotated MP4 output video.")

        active_tracks: dict[int, VehicleTrack] = {}
        events: list[Violation] = []
        confirmed_ids: set[int] = set()
        vehicle_summaries: dict[int, dict[str, object]] = {}
        frame_index = 0
        warmup_s = 0.5
        history_window_s = 2.0

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                timestamp_s = frame_index / fps
                visible_ids: set[int] = set()

                if timestamp_s >= warmup_s:
                    result = self.model.track(
                        frame,
                        persist=True,
                        tracker="bytetrack.yaml",
                        classes=[2, 3, 5, 7],
                        conf=self.config.confidence,
                        imgsz=self.config.image_size,
                        device="cpu",
                        verbose=False,
                    )[0]
                    if result.boxes is not None and result.boxes.id is not None:
                        boxes = result.boxes.xyxy.cpu().numpy()
                        ids = result.boxes.id.int().cpu().tolist()
                        for raw_box, raw_id in zip(boxes, ids):
                            track_id = int(raw_id)
                            box = tuple(int(value) for value in raw_box)
                            x1, y1, x2, y2 = box
                            image_box = (x1, y1, x2 - x1, y2 - y1)
                            world_x, world_y = self._world_position(homography, box)
                            track = active_tracks.get(track_id)
                            if track is None:
                                track = VehicleTrack(track_id, timestamp_s, timestamp_s, image_box)
                                active_tracks[track_id] = track

                            elapsed = timestamp_s - track.last_seen_s
                            displacement = 0.0
                            if track.world_history:
                                _, previous_x, previous_y = track.world_history[-1]
                                displacement = float(np.hypot(world_x - previous_x, world_y - previous_y))
                            max_step_m = self.config.max_plausible_speed_kmh / 3.6 * max(elapsed, 1.0 / fps) * 2.0

                            # A ByteTrack identity must also pass a physical continuity gate.
                            # Implausible jumps start a fresh track segment and cannot make a speed spike.
                            if track.world_history and (
                                elapsed > 0.5 or (elapsed > 0 and displacement > max_step_m)
                            ):
                                reported = set(track.reported)
                                track = VehicleTrack(track_id, timestamp_s, timestamp_s, image_box)
                                track.reported = reported
                                active_tracks[track_id] = track

                            track.last_seen_s = timestamp_s
                            track.image_box = image_box
                            track.missed_frames = 0
                            track.world_history.append((timestamp_s, world_x, world_y))
                            track.world_history = [
                                point for point in track.world_history
                                if timestamp_s - point[0] <= history_window_s
                            ]
                            estimated = estimate_speed_kmh(track.world_history)
                            if estimated is not None and estimated <= self.config.max_plausible_speed_kmh:
                                track.speed_history.append(estimated)
                                track.speed_history = track.speed_history[-9:]
                            elif estimated is not None:
                                # High readings are rejected as noisy associations, not displayed or reported.
                                track.world_history = track.world_history[:-1]
                            summary = vehicle_summaries.get(track_id)
                            if summary is None:
                                summary = {
                                    "vehicle_id": track_id,
                                    "first_seen_s": timestamp_s,
                                    "last_seen_s": timestamp_s,
                                    "speed_samples": [],
                                    "start_y": world_y,
                                    "end_y": world_y,
                                }
                                vehicle_summaries[track_id] = summary
                            summary["last_seen_s"] = timestamp_s
                            summary["end_y"] = world_y
                            if track.age_s >= self.config.minimum_track_age_s:
                                confirmed_ids.add(track_id)
                            if estimated is not None and estimated <= self.config.max_plausible_speed_kmh:
                                summary["speed_samples"].append(track.speed_kmh)
                            visible_ids.add(track_id)
                            events.extend(
                                evaluate_track(
                                    track,
                                    timestamp_s,
                                    self.config.speed_limit_kmh,
                                    self.config.expected_direction,
                                    persistence_frames=self.config.persistence_frames,
                                    minimum_track_age_s=self.config.minimum_track_age_s,
                                    maximum_plausible_speed_kmh=self.config.max_plausible_speed_kmh,
                                )
                            )

                            color = (50, 205, 120) if not track.reported else (40, 60, 235)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            label = f"ID {track_id} | {track.speed_kmh:.1f} km/h"
                            cv2.putText(frame, label, (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                for track_id, track in active_tracks.items():
                    if track_id not in visible_ids:
                        track.missed_frames += 1
                stale_ids = [track_id for track_id, track in active_tracks.items() if track.missed_frames > int(fps * 2)]
                for track_id in stale_ids:
                    del active_tracks[track_id]

                self._draw_calibration(frame, self.config.road_corners)
                cv2.putText(frame, f"Vehicles: {len(confirmed_ids)}  Events: {len(events)}", (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                writer.write(frame)
                frame_index += 1
                if progress and frame_index % max(1, int(fps / 2)) == 0:
                    progress(frame_index, total_frames, len(events))
        finally:
            capture.release()
            writer.release()

        confirmed_summaries = confirmed_vehicles(
            list(vehicle_summaries.values()), confirmed_ids
        )
        confirmed_events = [event for event in events if event.track_id in confirmed_ids]
        write_csv_report(
            output_csv,
            confirmed_summaries,
            confirmed_events,
            self.config.road_width_m,
            self.config.road_length_m,
        )

        return {
            "frames": frame_index,
            "vehicles": len(confirmed_ids),
            "events": len(confirmed_events),
            "duration_s": frame_index / fps,
        }

