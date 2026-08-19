from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import Any


@dataclass(frozen=True)
class Point:
    timestamp: datetime
    value: float


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _trend(values: list[float]) -> str:
    if len(values) < 2:
        return "insufficient_data"
    first, last = values[0], values[-1]
    delta = last - first
    scale = max(abs(first), 1.0)
    if abs(delta) <= 0.02 * scale:
        return "stable"
    return "increasing" if delta > 0 else "decreasing"


def _explain(name: str, values: list[float], unit: str) -> dict[str, Any]:
    if not values:
        return {
            "metric": name,
            "trend": "no_data",
            "severity": "info",
            "explanation": f"No {name} samples are available yet.",
            "recommendation": "Continue collecting telemetry.",
        }

    trend = _trend(values)
    delta = values[-1] - values[0] if len(values) > 1 else 0.0
    if trend == "increasing":
        direction = "increased"
    elif trend == "decreasing":
        direction = "decreased"
    elif trend == "stable":
        direction = "remained approximately stable"
    else:
        direction = "could not be determined"

    severity = "info"
    recommendation = "Continue monitoring."
    if name == "battery_percent" and values[-1] < 20:
        severity = "warning"
        recommendation = "Plan a battery recovery/recharge before the next mission."
    elif name == "battery_percent" and values[-1] < 10:
        severity = "critical"
        recommendation = "End the mission and recover the robot as soon as practical."
    elif name == "pressure_body_kpa" and abs(delta) > max(abs(values[0]) * 0.20, 10.0):
        severity = "warning"
        recommendation = "Inspect the morphology/pressure-control system and verify the target pressure."
    elif (
        name == "turbidity_ntu"
        and len(values) > 2
        and max(values) > 2 * max(sum(values) / len(values), 1.0)
    ):
        severity = "warning"
        recommendation = (
            "Review the corresponding video/map segment for sediment or obstruction."
        )

    return {
        "metric": name,
        "trend": trend,
        "start": values[0],
        "end": values[-1],
        "change": delta,
        "unit": unit,
        "severity": severity,
        "explanation": (
            f"{name.replace('_', ' ').capitalize()} {direction} by "
            f"{abs(delta):.2f} {unit} over the available telemetry window."
        ),
        "recommendation": recommendation,
    }


def _zscore_anomalies(points: list[Point]) -> list[dict[str, Any]]:
    values = [p.value for p in points]
    if len(values) < 8:
        return []
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = sqrt(variance)
    if std == 0:
        return []

    anomalies = []
    for point in points:
        z = (point.value - mean) / std
        if abs(z) >= 3:
            anomalies.append(
                {
                    "timestamp": point.timestamp,
                    "value": point.value,
                    "z_score": round(z, 3),
                }
            )
    return anomalies


def build_telemetry_analytics(rows: Iterable[Any]) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: row.timestamp)
    rows = list(rows)
    if not rows:
        return {
            "sample_count": 0,
            "start_time": None,
            "end_time": None,
            "duration_s": 0.0,
            "distance": {"start_m": None, "end_m": None, "change_m": 0.0},
            "latest_state": None,
            "series": {},
            "explanations": [],
            "anomalies": {},
        }

    rows.sort(key=lambda r: r.timestamp)
    first, last = rows[0], rows[-1]

    def make_points(getter) -> list[Point]:
        result: list[Point] = []
        for row in rows:
            value = _safe_float(getter(row))
            if value is not None:
                result.append(Point(timestamp=row.timestamp, value=value))
        return result

    series_map = {
        "distance_m": (make_points(lambda r: r.distance_m), "m"),
        "body_diameter_mm": (make_points(lambda r: r.body_diameter_mm), "mm"),
        "battery_percent": (make_points(lambda r: r.battery_percent), "%"),
        "pressure_body_kpa": (
            make_points(lambda r: (r.pressure or {}).get("body_kpa")),
            "kPa",
        ),
        "pressure_front_anchor_kpa": (
            make_points(lambda r: (r.pressure or {}).get("front_anchor_kpa")),
            "kPa",
        ),
        "pressure_rear_anchor_kpa": (
            make_points(lambda r: (r.pressure or {}).get("rear_anchor_kpa")),
            "kPa",
        ),
        "water_temperature_c": (
            make_points(lambda r: (r.water or {}).get("temperature_c")),
            "°C",
        ),
        "ph": (make_points(lambda r: (r.water or {}).get("ph")), "pH"),
        "conductivity_ms_cm": (
            make_points(lambda r: (r.water or {}).get("conductivity_ms_cm")),
            "mS/cm",
        ),
        "turbidity_ntu": (
            make_points(lambda r: (r.water or {}).get("turbidity_ntu")),
            "NTU",
        ),
        "gyro_z": (make_points(lambda r: (r.imu or {}).get("gz")), "rad/s"),
    }

    series: dict[str, list[dict[str, Any]]] = {}
    explanations: list[dict[str, Any]] = []
    anomalies: dict[str, list[dict[str, Any]]] = {}

    for name, (points, unit) in series_map.items():
        series[name] = [{"timestamp": p.timestamp, "value": p.value} for p in points]
        if points:
            explanations.append(_explain(name, [p.value for p in points], unit))
            found = _zscore_anomalies(points)
            if found:
                anomalies[name] = found

    distance_points = series_map["distance_m"][0]
    start_distance = distance_points[0].value if distance_points else None
    end_distance = distance_points[-1].value if distance_points else None

    duration = (last.timestamp - first.timestamp).total_seconds()

    return {
        "sample_count": len(rows),
        "start_time": first.timestamp,
        "end_time": last.timestamp,
        "duration_s": max(duration, 0.0),
        "distance": {
            "start_m": start_distance,
            "end_m": end_distance,
            "change_m": (end_distance - start_distance)
            if start_distance is not None and end_distance is not None
            else 0.0,
        },
        "latest_state": last.state,
        "series": series,
        "explanations": explanations,
        "anomalies": anomalies,
    }
