from datetime import datetime, timezone
from types import SimpleNamespace

from backend.app.services.graph_engine import build_distance_indexed_charts


def make_row(
    ts: int,
    distance: float,
    diameter: float,
    battery: float,
    turbidity: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
        distance_m=distance,
        body_diameter_mm=diameter,
        battery_percent=battery,
        state="INSPECTING",
        pressure={
            "body_kpa": 95.0,
            "front_anchor_kpa": 175.0,
            "rear_anchor_kpa": 170.0,
        },
        water={
            "temperature_c": 25.0,
            "ph": 6.9,
            "conductivity_ms_cm": 1.6,
            "turbidity_ntu": turbidity,
        },
        imu={"gz": 0.02},
    )


def test_graphs_are_distance_indexed_and_time_ordered():
    rows = [
        make_row(3, 2.0, 112.0, 98.0, 34.0),
        make_row(1, 0.0, 105.0, 100.0, 30.0),
        make_row(2, 1.0, 109.0, 99.0, 32.0),
    ]

    result = build_distance_indexed_charts(rows)
    assert result["chart_count"] == 10

    points = result["charts"]["body_diameter_mm"]["points"]
    assert [p["distance_m"] for p in points] == [0.0, 1.0, 2.0]
    assert [p["value"] for p in points] == [105.0, 109.0, 112.0]


def test_chart_contains_axis_metadata():
    rows = [make_row(1, 0.0, 105.0, 100.0, 30.0)]
    result = build_distance_indexed_charts(rows)
    chart = result["charts"]["turbidity_ntu"]

    assert chart["x_axis"]["field"] == "distance_m"
    assert chart["x_axis"]["unit"] == "m"
    assert chart["y_axis"]["unit"] == "NTU"
