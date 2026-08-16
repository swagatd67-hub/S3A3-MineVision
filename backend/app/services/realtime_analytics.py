from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Telemetry
from backend.app.services.cross_sensor import build_cross_sensor_events


def build_live_analytics_update(
    db: Session,
    *,
    mission_id: str,
    telemetry_row: Telemetry,
    history_limit: int = 25,
) -> dict[str, Any]:
    """Build the incremental analytics payload for a newly received packet.

    The payload is intentionally compact:
    - the newest chart point for each available metric
    - the most recent cross-sensor events detected in the rolling window
    - the latest inspection position

    The database remains the source of truth; this function only computes the
    live update that should be broadcast to WebSocket clients.
    """
    rows = db.scalars(
        select(Telemetry)
        .where(Telemetry.mission_id == mission_id)
        .order_by(Telemetry.timestamp.desc())
        .limit(history_limit)
    ).all()
    rows = list(reversed(rows))

    latest_points = _latest_points(telemetry_row)

    events = build_cross_sensor_events(rows)

    return {
        "type": "analytics_update",
        "mission_id": mission_id,
        "distance_m": telemetry_row.distance_m,
        "timestamp": telemetry_row.timestamp.isoformat(),
        "latest_points": latest_points,
        "recent_events": events[-10:],
        "new_event": events[-1] if events else None,
    }


def _latest_points(row: Telemetry) -> dict[str, dict[str, Any]]:
    points: dict[str, dict[str, Any]] = {}

    def add(metric: str, value: Any, unit: str) -> None:
        if value is None:
            return
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return

        points[metric] = {
            "metric": metric,
            "distance_m": row.distance_m,
            "timestamp": row.timestamp.isoformat(),
            "value": numeric,
            "unit": unit,
        }

    add("body_diameter_mm", row.body_diameter_mm, "mm")
    add("battery_percent", row.battery_percent, "%")

    pressure = row.pressure or {}
    add("pressure_body_kpa", pressure.get("body_kpa"), "kPa")
    add("pressure_front_anchor_kpa", pressure.get("front_anchor_kpa"), "kPa")
    add("pressure_rear_anchor_kpa", pressure.get("rear_anchor_kpa"), "kPa")

    water = row.water or {}
    add("water_temperature_c", water.get("temperature_c"), "°C")
    add("ph", water.get("ph"), "pH")
    add("conductivity_ms_cm", water.get("conductivity_ms_cm"), "mS/cm")
    add("turbidity_ntu", water.get("turbidity_ntu"), "NTU")

    imu = row.imu or {}
    add("gyro_z", imu.get("gz"), "rad/s")

    return points
