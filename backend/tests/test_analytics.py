from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.app.services.analytics import build_telemetry_analytics


def row(i: int) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=datetime(2026, 8, 16, tzinfo=timezone.utc) + timedelta(seconds=i),
        distance_m=float(i),
        body_diameter_mm=100.0 + i,
        battery_percent=100.0 - i,
        state="INSPECTING",
        imu={"gz": 0.1 + i * 0.01},
        pressure={"body_kpa": 90.0 + i},
        water={
            "temperature_c": 25.0 + i * 0.1,
            "ph": 6.9,
            "conductivity_ms_cm": 1.6,
            "turbidity_ntu": 30.0 + i,
        },
    )


def test_build_telemetry_analytics():
    result = build_telemetry_analytics([row(i) for i in range(10)])

    assert result["sample_count"] == 10
    assert result["distance"]["change_m"] == 9.0
    assert len(result["series"]["distance_m"]) == 10
    assert result["latest_state"] == "INSPECTING"
    assert any(e["metric"] == "battery_percent" for e in result["explanations"])
