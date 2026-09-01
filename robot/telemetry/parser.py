"""Typed Parser and Validator for Robot Telemetry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from robot.telemetry.exceptions import TelemetryParseError, TelemetryValidationError
from robot.telemetry.models import (
    IMUData,
    PressureData,
    RobotTelemetry,
    WaterQualityData,
)


def _parse_timestamp(val: Any) -> datetime | None:
    if val is None:
        return None

    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val

    if isinstance(val, str):
        try:
            cleaned = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError) as err:
            raise TelemetryValidationError(
                f"Invalid timestamp string format '{val}': {err}"
            ) from err

    raise TelemetryValidationError(
        f"Invalid timestamp type: {type(val).__name__}"
    )


def _get_float_or_none(data: dict[str, Any], field: str) -> float | None:
    val = data.get(field)
    if val is None:
        return None
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise TelemetryValidationError(
            f"Field '{field}' must be numeric, got {type(val).__name__} ({val!r})."
        )
    return float(val)


def parse_telemetry(raw: dict[str, Any] | str | None) -> RobotTelemetry | None:
    """Parse raw telemetry payload into typed RobotTelemetry model.

    Does NOT mutate the input payload.
    Does NOT use command protocol commands.json.
    """
    if raw is None:
        return None

    if isinstance(raw, str):
        try:
            data_dict = json.loads(raw)
        except Exception as err:
            raise TelemetryParseError(
                f"Malformed JSON telemetry string: {err}"
            ) from err

        if not isinstance(data_dict, dict):
            raise TelemetryValidationError("JSON content must be an object.")
        data = dict(data_dict)
    elif isinstance(raw, dict):
        data = dict(raw)
    else:
        raise TelemetryValidationError(
            f"Unsupported telemetry payload type: {type(raw).__name__}"
        )

    # Distinguish command dictionaries from telemetry packets
    if "name" in data and "robot_id" not in data:
        raise TelemetryValidationError(
            "Input message appears to be a command payload, not a telemetry packet."
        )

    robot_id = data.get("robot_id")
    if not isinstance(robot_id, str) or not robot_id.strip():
        raise TelemetryValidationError(
            "Missing or invalid required field 'robot_id'."
        )

    mission_id = data.get("mission_id")
    if mission_id is not None and not isinstance(mission_id, str):
        raise TelemetryValidationError(
            f"Field 'mission_id' must be a string or None, got {type(mission_id).__name__}."
        )

    state = data.get("state", "IDLE")
    if not isinstance(state, str):
        raise TelemetryValidationError(
            f"Field 'state' must be a string, got {type(state).__name__}."
        )

    battery_percent = _get_float_or_none(data, "battery_percent")
    if battery_percent is not None and (
        battery_percent < 0.0 or battery_percent > 100.0
    ):
        raise TelemetryValidationError(
            f"battery_percent {battery_percent} out of valid range [0, 100]."
        )

    distance_m = _get_float_or_none(data, "distance_m")
    if distance_m is not None and distance_m < 0.0:
        raise TelemetryValidationError(
            f"distance_m {distance_m} cannot be negative."
        )

    body_diameter_mm = _get_float_or_none(data, "body_diameter_mm")
    if body_diameter_mm is not None and body_diameter_mm < 0.0:
        raise TelemetryValidationError(
            f"body_diameter_mm {body_diameter_mm} cannot be negative."
        )

    timestamp = _parse_timestamp(data.get("timestamp"))

    # IMU parsing
    imu_obj: IMUData | None = None
    imu_raw = data.get("imu")
    if imu_raw is not None:
        if not isinstance(imu_raw, dict):
            raise TelemetryValidationError("Field 'imu' must be a dictionary.")

        imu_fields = ("ax", "ay", "az", "gx", "gy", "gz")
        imu_vals: dict[str, float | None] = {}
        for f in imu_fields:
            val = imu_raw.get(f)
            if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
                raise TelemetryValidationError(
                    f"IMU field '{f}' must be numeric, got {val!r}."
                )
            imu_vals[f] = float(val)

        imu_temperature = _get_float_or_none(imu_raw, "temperature_c")
        imu_vals["temperature_c"] = imu_temperature

        imu_obj = IMUData(**imu_vals)

    # Pressure parsing
    press_obj: PressureData | None = None
    press_raw = data.get("pressure")
    if press_raw is not None:
        if not isinstance(press_raw, dict):
            raise TelemetryValidationError("Field 'pressure' must be a dictionary.")

        body_kpa = _get_float_or_none(press_raw, "body_kpa")
        front_kpa = _get_float_or_none(press_raw, "front_anchor_kpa")
        rear_kpa = _get_float_or_none(press_raw, "rear_anchor_kpa")

        press_obj = PressureData(
            body_kpa=body_kpa,
            front_anchor_kpa=front_kpa,
            rear_anchor_kpa=rear_kpa,
        )

    # Water parsing
    water_obj: WaterQualityData | None = None
    water_raw = data.get("water")
    if water_raw is not None:
        if not isinstance(water_raw, dict):
            raise TelemetryValidationError("Field 'water' must be a dictionary.")

        temp_c = _get_float_or_none(water_raw, "temperature_c")
        ph_val = _get_float_or_none(water_raw, "ph")
        cond_val = _get_float_or_none(water_raw, "conductivity_ms_cm")
        turb_val = _get_float_or_none(water_raw, "turbidity_ntu")

        water_obj = WaterQualityData(
            temperature_c=temp_c,
            ph=ph_val,
            conductivity_ms_cm=cond_val,
            turbidity_ntu=turb_val,
        )

    return RobotTelemetry(
        robot_id=robot_id,
        mission_id=mission_id,
        timestamp=timestamp,
        battery_percent=battery_percent,
        distance_m=distance_m,
        body_diameter_mm=body_diameter_mm,
        state=state,
        imu=imu_obj,
        pressure=press_obj,
        water=water_obj,
    )
