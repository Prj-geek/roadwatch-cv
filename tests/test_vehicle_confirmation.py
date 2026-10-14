from roadwatch.reporting import confirmed_vehicles


def test_vehicle_count_excludes_short_lived_track_ids():
    tracks = [
        {"vehicle_id": 1, "first_seen_s": 0.53, "last_seen_s": 2.88},
        {"vehicle_id": 2, "first_seen_s": 0.53, "last_seen_s": 0.60},
        {"vehicle_id": 3, "first_seen_s": 0.53, "last_seen_s": 2.09},
        {"vehicle_id": 6, "first_seen_s": 0.70, "last_seen_s": 1.43},
        {"vehicle_id": 10, "first_seen_s": 0.83, "last_seen_s": 3.91},
        {"vehicle_id": 12, "first_seen_s": 0.99, "last_seen_s": 0.99},
        {"vehicle_id": 13, "first_seen_s": 1.06, "last_seen_s": 1.29},
    ]

    confirmed = confirmed_vehicles(tracks, {1, 3, 10})

    assert [track["vehicle_id"] for track in confirmed] == [1, 3, 10]
