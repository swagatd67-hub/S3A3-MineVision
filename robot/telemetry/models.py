"""PipeVision Robot Telemetry Data Models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IMUData:
    """Inertial Measurement Unit (IMU) telemetry model.

    Units:
        ax, ay, az: Linear acceleration in meters per second squared (m/s²)
        gx, gy, gz: Angular velocity / gyro rates
    """

    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    temperature_c: float | None = None


@dataclass(frozen=True)
class PressureData:
    """Pressure sensors telemetry model.

    Units:
        body_kpa: Internal body pressure in kilopascals (kPa)
        front_anchor_kpa: Front crawler anchor pressure in kilopascals (kPa)
        rear_anchor_kpa: Rear crawler anchor pressure in kilopascals (kPa)
    """

    body_kpa: float | None = None
    front_anchor_kpa: float | None = None
    rear_anchor_kpa: float | None = None


@dataclass(frozen=True)
class WaterQualityData:
    """Water quality sensors telemetry model.

    Units:
        temperature_c: Water temperature in degrees Celsius (°C)
        ph: Water pH level (0-14 pH scale)
        conductivity_ms_cm: Electrical conductivity in millisiemens per centimeter (mS/cm)
        turbidity_ntu: Water turbidity in Nephelometric Turbidity Units (NTU)
    """

    temperature_c: float | None = None
    ph: float | None = None
    conductivity_ms_cm: float | None = None
    turbidity_ntu: float | None = None


@dataclass(frozen=True)
class RobotTelemetry:
    """Top-level PipeVision Robot Telemetry model.

    Units / Specifications:
        robot_id: Unique robot identifier (str)
        mission_id: Unique mission identifier (str | None)
        timestamp: Timezone-aware UTC timestamp (datetime | None)
        battery_percent: Remaining battery capacity in percent (0.0% to 100.0%)
        distance_m: Distance traveled along pipe in meters (m)
        body_diameter_mm: Adjustable crawler body diameter in millimeters (mm)
        state: Current robot operational state string
        imu: IMU telemetry sub-packet (IMUData | None)
        pressure: Pressure telemetry sub-packet (PressureData | None)
        water: Water quality telemetry sub-packet (WaterQualityData | None)
    """

    robot_id: str
    mission_id: str | None = None
    timestamp: datetime | None = None
    battery_percent: float | None = None
    distance_m: float | None = None
    body_diameter_mm: float | None = None
    state: str = "IDLE"
    imu: IMUData | None = None
    pressure: PressureData | None = None
    water: WaterQualityData | None = None
