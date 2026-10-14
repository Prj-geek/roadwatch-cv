import pytest

from roadwatch.rules import estimate_speed_kmh


def test_speed_ignores_lateral_lane_change_displacement():
    history = [(0.0, 0.0, 0.0), (0.8, 20.0, 4.0)]

    assert estimate_speed_kmh(history) == pytest.approx(18.0)
