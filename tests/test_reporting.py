import csv

from roadwatch.reporting import write_csv_report


def test_report_contains_vehicle_rows_even_without_violations(tmp_path):
    report = tmp_path / "events.csv"
    vehicles = [
        {
            "vehicle_id": 12,
            "first_seen_s": 0.5,
            "last_seen_s": 2.0,
            "speed_samples": [27.0, 29.0, 28.0],
            "start_y": 1.0,
            "end_y": 8.0,
        }
    ]

    write_csv_report(report, vehicles, [], 7.0, 25.0)

    with report.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["record_type"] == "vehicle"
    assert rows[0]["vehicle_id"] == "12"
    assert rows[0]["median_speed_kmh"] == "28.00"
    assert rows[0]["event"] == "none"


def test_report_explains_when_no_vehicles_were_detected(tmp_path):
    report = tmp_path / "events.csv"

    write_csv_report(report, [], [], 7.0, 25.0)

    with report.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["record_type"] == "run_summary"
    assert rows[0]["details"] == "No vehicles were detected in the video."
