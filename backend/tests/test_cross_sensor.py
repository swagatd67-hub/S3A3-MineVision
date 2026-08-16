from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.services.cross_sensor import build_cross_sensor_events


def row(
    distance: float,
    diameter: float,
    pressure: float,
    turbidity: float,
    gyro: float = 0.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=distance),
        distance_m=distance,
        body_diameter_mm=diameter,
        battery_percent=90.0,
        state="INSPECTING",
        pressure={
            "body_kpa": pressure,
            "front_anchor_kpa": 175.0,
            "rear_anchor_kpa": 170.0,
        },
        water={
            "temperature_c": 25.0,
            "ph": 6.9,
            "conductivity_ms_cm": 1.6,
            "turbidity_ntu": turbidity,
        },
        imu={"gz": gyro},
    )


def test_detects_possible_obstruction():
    rows = [
        row(10.0, 110.0, 95.0, 30.0),
        row(10.5, 107.0, 98.0, 35.0),
    ]

    events = build_cross_sensor_events(rows)

    assert len(events) == 1
    assert events[0]["event_type"] == "POSSIBLE_OBSTRUCTION"
    assert events[0]["distance_start_m"] == 10.0
    assert events[0]["distance_end_m"] == 10.5
    assert "turbidity_increase" in events[0]["evidence"]


def test_detects_morphology_pressure_anomaly():
    rows = [
        row(20.0, 110.0, 95.0, 30.0),
        row(20.5, 106.0, 92.0, 30.0),
    ]

    events = build_cross_sensor_events(rows)

    assert len(events) == 1
    assert events[0]["event_type"] == "MORPHOLOGY_PRESSURE_ANOMALY"


def test_no_event_for_normal_transition():
    rows = [
        row(30.0, 110.0, 95.0, 30.0),
        row(30.5, 110.5, 95.5, 30.5),
    ]

    assert build_cross_sensor_events(rows) == []
