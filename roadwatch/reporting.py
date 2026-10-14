"""CSV report generation for vehicle observations and violation events."""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence


REPORT_COLUMNS = [
    "record_type",
    "vehicle_id",
    "first_seen_seconds",
    "last_seen_seconds",
    "observed_duration_seconds",
    "median_speed_kmh",
    "max_speed_kmh",
    "direction",
    "event",
    "timestamp_seconds",
    "event_speed_kmh",
    "details",
    "calibration_road_width_m",
    "calibration_road_length_m",
]


def confirmed_vehicles(
    vehicles: Sequence[Mapping[str, object]], confirmed_ids: set[int]
) -> list[Mapping[str, object]]:
    """Keep only tracks that passed the live continuous-duration confirmation."""
    return [
        vehicle
        for vehicle in vehicles
        if int(vehicle["vehicle_id"]) in confirmed_ids
    ]


def write_csv_report(
    output_csv: Path,
    vehicles: Sequence[Mapping[str, object]],
    events: Sequence[object],
    road_width_m: float,
    road_length_m: float,
) -> None:
    """Write vehicle observations as well as violations, including empty-run status."""
    vehicle_by_id = {int(vehicle["vehicle_id"]): vehicle for vehicle in vehicles}
    events_by_id: dict[int, list[str]] = {}
    for event in events:
        events_by_id.setdefault(int(event.track_id), []).append(str(event.kind))

    with output_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
        writer.writeheader()

        for vehicle in vehicles:
            speeds = [float(speed) for speed in vehicle["speed_samples"]]
            start_y = float(vehicle["start_y"])
            end_y = float(vehicle["end_y"])
            direction = "forward" if end_y - start_y > 0.2 else "reverse" if end_y - start_y < -0.2 else "unclear"
            first_seen = float(vehicle["first_seen_s"])
            last_seen = float(vehicle["last_seen_s"])
            writer.writerow(
                {
                    "record_type": "vehicle",
                    "vehicle_id": vehicle["vehicle_id"],
                    "first_seen_seconds": f"{first_seen:.2f}",
                    "last_seen_seconds": f"{last_seen:.2f}",
                    "observed_duration_seconds": f"{last_seen - first_seen:.2f}",
                    "median_speed_kmh": f"{median(speeds):.2f}" if speeds else "",
                    "max_speed_kmh": f"{max(speeds):.2f}" if speeds else "",
                    "direction": direction,
                    "event": ";".join(events_by_id.get(int(vehicle["vehicle_id"]), [])) or "none",
                    "calibration_road_width_m": f"{road_width_m:.2f}",
                    "calibration_road_length_m": f"{road_length_m:.2f}",
                }
            )

        for event in events:
            vehicle = vehicle_by_id.get(int(event.track_id), {})
            first_seen = float(vehicle.get("first_seen_s", 0.0))
            last_seen = float(vehicle.get("last_seen_s", 0.0))
            writer.writerow(
                {
                    "record_type": "violation",
                    "vehicle_id": event.track_id,
                    "first_seen_seconds": f"{first_seen:.2f}" if vehicle else "",
                    "last_seen_seconds": f"{last_seen:.2f}" if vehicle else "",
                    "observed_duration_seconds": f"{last_seen - first_seen:.2f}" if vehicle else "",
                    "direction": "",
                    "event": event.kind,
                    "timestamp_seconds": f"{event.timestamp_s:.2f}",
                    "event_speed_kmh": f"{event.speed_kmh:.2f}",
                    "details": event.details,
                    "calibration_road_width_m": f"{road_width_m:.2f}",
                    "calibration_road_length_m": f"{road_length_m:.2f}",
                }
            )

        if not vehicles:
            writer.writerow(
                {
                    "record_type": "run_summary",
                    "event": "none",
                    "details": "No vehicles were detected in the video.",
                    "calibration_road_width_m": f"{road_width_m:.2f}",
                    "calibration_road_length_m": f"{road_length_m:.2f}",
                }
            )
