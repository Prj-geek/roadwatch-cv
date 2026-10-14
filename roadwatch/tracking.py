"""Small dependency-free centroid tracker used by the video pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Iterable


Point = tuple[float, float]
Box = tuple[int, int, int, int]


@dataclass
class Track:
    track_id: int
    centroid: Point
    box: Box
    first_seen_s: float
    last_seen_s: float
    missed: int = 0
    history: list[tuple[float, Point]] = field(default_factory=list)
    speeds_kmh: list[float] = field(default_factory=list)
    overspeed_frames: int = 0
    wrong_way_frames: int = 0
    reported: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append((self.first_seen_s, self.centroid))

    @property
    def speed_kmh(self) -> float:
        if not self.speeds_kmh:
            return 0.0
        window = self.speeds_kmh[-5:]
        return sum(window) / len(window)

    @property
    def displacement(self) -> Point:
        origin = self.history[0][1]
        return self.centroid[0] - origin[0], self.centroid[1] - origin[1]


class CentroidTracker:
    def __init__(self, max_distance: float = 90.0, max_missed: int = 10) -> None:
        self.max_distance = max_distance
        self.max_missed = max_missed
        self.tracks: dict[int, Track] = {}
        self._next_id = 1

    @staticmethod
    def _centroid(box: Box) -> Point:
        x, y, w, h = box
        return x + w / 2.0, y + h / 2.0

    def update(self, boxes: Iterable[Box], timestamp_s: float) -> list[Track]:
        detections = [(box, self._centroid(box)) for box in boxes]
        unmatched_tracks = set(self.tracks)
        unmatched_detections = set(range(len(detections)))

        candidates: list[tuple[float, int, int]] = []
        for track_id, track in self.tracks.items():
            for detection_index, (_, centroid) in enumerate(detections):
                distance = hypot(
                    track.centroid[0] - centroid[0],
                    track.centroid[1] - centroid[1],
                )
                if distance <= self.max_distance:
                    candidates.append((distance, track_id, detection_index))

        for _, track_id, detection_index in sorted(candidates):
            if track_id not in unmatched_tracks or detection_index not in unmatched_detections:
                continue
            box, centroid = detections[detection_index]
            track = self.tracks[track_id]
            elapsed = timestamp_s - track.last_seen_s
            if elapsed > 0:
                pixels = hypot(
                    centroid[0] - track.centroid[0], centroid[1] - track.centroid[1]
                )
                track.speeds_kmh.append(pixels / elapsed)
            track.centroid = centroid
            track.box = box
            track.last_seen_s = timestamp_s
            track.missed = 0
            track.history.append((timestamp_s, centroid))
            track.history = track.history[-60:]
            unmatched_tracks.remove(track_id)
            unmatched_detections.remove(detection_index)

        for track_id in unmatched_tracks:
            self.tracks[track_id].missed += 1

        expired = [
            track_id
            for track_id, track in self.tracks.items()
            if track.missed > self.max_missed
        ]
        for track_id in expired:
            del self.tracks[track_id]

        for detection_index in unmatched_detections:
            box, centroid = detections[detection_index]
            track_id = self._next_id
            self._next_id += 1
            self.tracks[track_id] = Track(
                track_id=track_id,
                centroid=centroid,
                box=box,
                first_seen_s=timestamp_s,
                last_seen_s=timestamp_s,
            )

        return [track for track in self.tracks.values() if track.missed == 0]

