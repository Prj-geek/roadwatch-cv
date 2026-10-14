import pytest

from roadwatch.rules import convert_track_speed, evaluate_track, movement_matches_direction
from roadwatch.tracking import CentroidTracker


def test_tracker_preserves_id_for_nearby_detection():
    tracker = CentroidTracker(max_distance=30, max_missed=2)
    first = tracker.update([(10, 10, 20, 20)], 0.0)
    second = tracker.update([(20, 10, 20, 20)], 1.0)
    assert first[0].track_id == second[0].track_id
    assert second[0].displacement == (10.0, 0.0)


def test_speed_conversion_uses_pixels_per_metre():
    tracker = CentroidTracker(max_distance=100)
    tracker.update([(0, 0, 10, 10)], 0.0)
    track = tracker.update([(20, 0, 10, 10)], 1.0)[0]
    assert convert_track_speed(track, pixels_per_metre=10) == pytest.approx(7.2)


def test_wrong_way_requires_meaningful_displacement():
    tracker = CentroidTracker(max_distance=100)
    track = tracker.update([(20, 0, 10, 10)], 0.0)[0]
    assert movement_matches_direction(track, "right")
    track = tracker.update([(0, 0, 10, 10)], 1.0)[0]
    assert not movement_matches_direction(track, "right")


def test_violation_is_emitted_once_after_persistence():
    tracker = CentroidTracker(max_distance=100)
    track = tracker.update([(0, 0, 10, 10)], 0.0)[0]
    emitted = []
    for second in range(1, 6):
        track = tracker.update([(second * 20, 0, 10, 10)], float(second))[0]
        emitted.extend(evaluate_track(track, second, 10, 5, "right", persistence_frames=3))
    assert [event.kind for event in emitted] == ["overspeed"]

