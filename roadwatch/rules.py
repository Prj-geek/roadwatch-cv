"""Metric speed and persistent rule evaluation for road-plane tracks."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median


@dataclass(frozen=True)
class Violation:
    kind: str
    track_id: int
    timestamp_s: float
    speed_kmh: float
    details: str


@dataclass
class VehicleTrack:
    track_id: int
    first_seen_s: float
    last_seen_s: float
    image_box: tuple[int, int, int, int]
    world_history: list[tuple[float, float, float]] = field(default_factory=list)
    speed_history: list[float] = field(default_factory=list)
    overspeed_frames: int = 0
    wrong_way_frames: int = 0
    reported: set[str] = field(default_factory=set)
    missed_frames: int = 0

    @property
    def age_s(self) -> float:
        return self.last_seen_s - self.first_seen_s

    @property
    def speed_kmh(self) -> float:
        return median(self.speed_history[-5:]) if self.speed_history else 0.0


def estimate_speed_kmh(
    history: list[tuple[float, float, float]],
    *,
    window_s: float = 0.8,
    minimum_window_s: float = 0.6,
) -> float | None:
    """Estimate speed from the net road-plane displacement across a stable window.

    Returns None until a track spans minimum_window_s. A median over available
    adjacent interval speeds limits sensitivity to occasional point jitter.
    """
    if len(history) < 2:
        return None
    end_t, end_x, end_y = history[-1]
    candidates = [point for point in history if end_t - point[0] >= minimum_window_s]
    if not candidates:
        return None
    start_t, start_x, start_y = min(
        candidates,
        key=lambda point: abs((end_t - point[0]) - window_s),
    )
    elapsed = end_t - start_t
    if elapsed <= 0:
        return None
    # Speed is measured along the road axis. The transverse coordinate remains
    # useful for tracking, but lane changes must not inflate road speed.
    distance_m = abs(end_y - start_y)
    return distance_m / elapsed * 3.6


def evaluate_track(
    track: VehicleTrack,
    timestamp_s: float,
    speed_limit_kmh: float,
    expected_direction: str,
    persistence_frames: int = 15,
    minimum_track_age_s: float = 1.0,
    maximum_plausible_speed_kmh: float = 160.0,
) -> list[Violation]:
    """Apply threshold rules only to mature, physically plausible tracks."""
    speed = track.speed_kmh
    if track.age_s < minimum_track_age_s or speed <= 0 or speed > maximum_plausible_speed_kmh:
        track.overspeed_frames = 0
        track.wrong_way_frames = 0
        return []

    latest = track.world_history[-1]
    past = next(
        (point for point in reversed(track.world_history[:-1]) if latest[0] - point[0] >= 0.6),
        None,
    )
    if past is None:
        return []
    longitudinal_delta = latest[2] - past[2]
    wrong_way = (
        longitudinal_delta < -0.2
        if expected_direction == "forward"
        else longitudinal_delta > 0.2
    )

    track.overspeed_frames = track.overspeed_frames + 1 if speed > speed_limit_kmh else 0
    track.wrong_way_frames = track.wrong_way_frames + 1 if wrong_way else 0
    violations: list[Violation] = []
    if track.overspeed_frames >= persistence_frames and "overspeed" not in track.reported:
        track.reported.add("overspeed")
        violations.append(
            Violation("overspeed", track.track_id, timestamp_s, speed, f"Limit {speed_limit_kmh:.0f} km/h")
        )
    if track.wrong_way_frames >= persistence_frames and "wrong_way" not in track.reported:
        track.reported.add("wrong_way")
        violations.append(
            Violation("wrong_way", track.track_id, timestamp_s, speed, f"Expected {expected_direction} road travel")
        )
    return violations

