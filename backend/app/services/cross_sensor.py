from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SensorSnapshot:
    distance_m: float
    body_diameter_mm: float | None
    body_pressure_kpa: float | None
    turbidity_ntu: float | None
    gyro_z: float | None
    battery_percent: float | None


def build_cross_sensor_events(
    rows: Iterable[Any],
    *,
    window_size: int = 5,
) -> list[dict[str, Any]]:
    """Generate distance-linked inspection events from multiple telemetry signals.

    These are screening events, not definitive diagnoses. They are intended to
    point an operator toward a pipe segment for video/map confirmation.
    """
    ordered = sorted(
        [r for r in rows if getattr(r, "distance_m", None) is not None],
        key=lambda r: r.timestamp,
    )

    if len(ordered) < 2:
        return []

    snapshots = [_snapshot(row) for row in ordered]
    events: list[dict[str, Any]] = []

    for index in range(1, len(snapshots)):
        current = snapshots[index]
        previous = snapshots[index - 1]

        diameter_delta = _delta(current.body_diameter_mm, previous.body_diameter_mm)
        pressure_delta = _delta(current.body_pressure_kpa, previous.body_pressure_kpa)
        turbidity_delta = _delta(current.turbidity_ntu, previous.turbidity_ntu)
        gyro_delta = _delta(current.gyro_z, previous.gyro_z)

        evidence: list[str] = []

        # Heuristic obstruction/sediment screen:
        # turbidity rises + body diameter contracts + body pressure rises.
        if (
            turbidity_delta is not None
            and diameter_delta is not None
            and pressure_delta is not None
            and turbidity_delta >= 4.0
            and diameter_delta <= -2.0
            and pressure_delta >= 2.0
        ):
            evidence = [
                "turbidity_increase",
                "diameter_decrease",
                "pressure_increase",
            ]
            events.append(
                _event(
                    event_type="POSSIBLE_OBSTRUCTION",
                    current=current,
                    previous=previous,
                    severity="warning",
                    evidence=evidence,
                    explanation=(
                        "Turbidity increased while body diameter decreased and "
                        "body pressure increased over the same short segment."
                    ),
                    recommendation=(
                        "Review the corresponding video and map segment for "
                        "sediment, debris, or restricted clearance."
                    ),
                )
            )
            continue

        # Morphology/pressure screening:
        # body contracts + pressure drops.
        if (
            diameter_delta is not None
            and pressure_delta is not None
            and diameter_delta <= -2.0
            and pressure_delta <= -2.0
        ):
            events.append(
                _event(
                    event_type="MORPHOLOGY_PRESSURE_ANOMALY",
                    current=current,
                    previous=previous,
                    severity="warning",
                    evidence=["diameter_decrease", "pressure_decrease"],
                    explanation=(
                        "Body diameter and body pressure decreased together "
                        "over the same telemetry interval."
                    ),
                    recommendation=(
                        "Inspect the morphology/pressure-control system and "
                        "confirm the pipe geometry with video."
                    ),
                )
            )
            continue

        # Collision/entanglement screening:
        # sudden gyro change + diameter change.
        if (
            gyro_delta is not None
            and diameter_delta is not None
            and abs(gyro_delta) >= 0.08
            and abs(diameter_delta) >= 4.0
        ):
            events.append(
                _event(
                    event_type="POSSIBLE_COLLISION",
                    current=current,
                    previous=previous,
                    severity="warning",
                    evidence=["imu_change", "diameter_change"],
                    explanation=(
                        "A sudden orientation change coincided with a body "
                        "diameter change."
                    ),
                    recommendation=(
                        "Review the video around this distance for contact, "
                        "entanglement, or an abrupt pipe transition."
                    ),
                )
            )
            continue

    return _merge_adjacent_events(events, window_size=window_size)


def _snapshot(row: Any) -> SensorSnapshot:
    pressure = row.pressure or {}
    water = row.water or {}
    imu = row.imu or {}

    return SensorSnapshot(
        distance_m=float(row.distance_m),
        body_diameter_mm=_float(row.body_diameter_mm),
        body_pressure_kpa=_float(pressure.get("body_kpa")),
        turbidity_ntu=_float(water.get("turbidity_ntu")),
        gyro_z=_float(imu.get("gz")),
        battery_percent=_float(row.battery_percent),
    )


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _event(
    *,
    event_type: str,
    current: SensorSnapshot,
    previous: SensorSnapshot,
    severity: str,
    evidence: list[str],
    explanation: str,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "distance_start_m": round(previous.distance_m, 3),
        "distance_end_m": round(current.distance_m, 3),
        "severity": severity,
        "evidence": evidence,
        "explanation": explanation,
        "recommendation": recommendation,
    }


def _merge_adjacent_events(
    events: list[dict[str, Any]],
    *,
    window_size: int,
) -> list[dict[str, Any]]:
    """Collapse repeated trigger samples into one distance region."""
    if not events:
        return []

    merged: list[dict[str, Any]] = [events[0].copy()]

    for event in events[1:]:
        last = merged[-1]

        same_type = event["event_type"] == last["event_type"]
        close = event["distance_start_m"] - last["distance_end_m"] <= 0.5

        if same_type and close:
            last["distance_end_m"] = event["distance_end_m"]
            last["evidence"] = sorted(set(last["evidence"]) | set(event["evidence"]))
            continue

        merged.append(event.copy())

    return merged
