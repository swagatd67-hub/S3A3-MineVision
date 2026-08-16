from datetime import datetime, timezone
from types import SimpleNamespace

from backend.app.services.realtime_analytics import _latest_points


def test_latest_points_are_distance_indexed():
    row = SimpleNamespace(
        distance_m=12.5,
        timestamp=datetime.now(timezone.utc),
        body_diameter_mm=110.0,
        battery_percent=88.0,
        pressure={
            "body_kpa": 96.0,
            "front_anchor_kpa": 175.0,
            "rear_anchor_kpa": 170.0,
        },
        water={
            "temperature_c": 25.2,
            "ph": 6.9,
            "conductivity_ms_cm": 1.6,
            "turbidity_ntu": 32.0,
        },
        imu={"gz": 0.05},
    )

    points = _latest_points(row)

    assert points["body_diameter_mm"]["distance_m"] == 12.5
    assert points["body_diameter_mm"]["value"] == 110.0
    assert points["battery_percent"]["value"] == 88.0
    assert points["water_temperature_c"]["value"] == 25.2
    assert points["gyro_z"]["unit"] == "rad/s"


def test_latest_points_skip_missing_values():
    row = SimpleNamespace(
        distance_m=1.0,
        timestamp=datetime.now(timezone.utc),
        body_diameter_mm=None,
        battery_percent=90.0,
        pressure=None,
        water=None,
        imu=None,
    )

    points = _latest_points(row)

    assert "body_diameter_mm" not in points
    assert "battery_percent" in points
