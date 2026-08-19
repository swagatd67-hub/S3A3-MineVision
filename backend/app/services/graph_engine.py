from __future__ import annotations

from collections.abc import Iterable
from typing import Any

METRIC_DEFINITIONS: dict[str, dict[str, str]] = {
    "body_diameter_mm": {"label": "Body Diameter", "unit": "mm"},
    "pressure_body_kpa": {"label": "Body Pressure", "unit": "kPa"},
    "pressure_front_anchor_kpa": {"label": "Front Anchor Pressure", "unit": "kPa"},
    "pressure_rear_anchor_kpa": {"label": "Rear Anchor Pressure", "unit": "kPa"},
    "battery_percent": {"label": "Battery", "unit": "%"},
    "water_temperature_c": {"label": "Water Temperature", "unit": "°C"},
    "ph": {"label": "pH", "unit": "pH"},
    "conductivity_ms_cm": {"label": "Conductivity", "unit": "mS/cm"},
    "turbidity_ntu": {"label": "Turbidity", "unit": "NTU"},
    "gyro_z": {"label": "Gyro Z", "unit": "rad/s"},
}


def build_distance_indexed_charts(rows: Iterable[Any]) -> dict[str, Any]:
    """Build frontend-ready distance-indexed chart data for one mission."""
    rows = sorted(rows, key=lambda r: r.timestamp)
    charts: dict[str, dict[str, Any]] = {}

    for metric, definition in METRIC_DEFINITIONS.items():
        points: list[dict[str, Any]] = []

        for row in rows:
            distance = _to_float(getattr(row, "distance_m", None))
            value = _extract_metric(row, metric)

            if distance is None or value is None:
                continue

            points.append(
                {
                    "distance_m": distance,
                    "timestamp": row.timestamp,
                    "value": value,
                }
            )

        if points:
            charts[metric] = {
                "metric": metric,
                "label": definition["label"],
                "unit": definition["unit"],
                "x_axis": {
                    "field": "distance_m",
                    "label": "Distance",
                    "unit": "m",
                },
                "y_axis": {
                    "field": "value",
                    "label": definition["label"],
                    "unit": definition["unit"],
                },
                "points": points,
            }

    return {"chart_count": len(charts), "charts": charts}


def _extract_metric(row: Any, metric: str) -> float | None:
    if metric in {"body_diameter_mm", "battery_percent"}:
        return _to_float(getattr(row, metric, None))

    if metric == "pressure_body_kpa":
        return _to_float((row.pressure or {}).get("body_kpa"))

    if metric == "pressure_front_anchor_kpa":
        return _to_float((row.pressure or {}).get("front_anchor_kpa"))

    if metric == "pressure_rear_anchor_kpa":
        return _to_float((row.pressure or {}).get("rear_anchor_kpa"))

    if metric == "water_temperature_c":
        return _to_float((row.water or {}).get("temperature_c"))

    if metric in {
        "ph",
        "conductivity_ms_cm",
        "turbidity_ntu",
    }:
        return _to_float((row.water or {}).get(metric))

    if metric == "gyro_z":
        return _to_float((row.imu or {}).get("gz"))

    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
