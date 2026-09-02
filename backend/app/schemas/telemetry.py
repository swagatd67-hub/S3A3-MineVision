from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IMUData(BaseModel):
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    temperature_c: float | None = None


class PressureData(BaseModel):
    body_kpa: float | None = None
    front_anchor_kpa: float | None = None
    rear_anchor_kpa: float | None = None


class WaterQualityData(BaseModel):
    temperature_c: float | None = None
    ph: float | None = None
    conductivity_ms_cm: float | None = None
    turbidity_ntu: float | None = None


class GasSensorData(BaseModel):
    sensor_id: str = "gas-01"
    sensor_type: str = "gas"
    value: float = Field(ge=0.0, le=100.0)
    status: Literal["NORMAL", "ELEVATED", "HIGH", "CRITICAL"] = "NORMAL"
    timestamp: datetime | str | None = None
    source: str = "local_simulator"


class TelemetryPacket(BaseModel):
    robot_id: str
    mission_id: str | None = None
    timestamp: datetime | None = None
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    imu: IMUData | None = None
    pressure: PressureData | None = None
    water: WaterQualityData | None = None
    gas: GasSensorData | None = None
    distance_m: float | None = Field(default=None, ge=0)
    body_diameter_mm: float | None = Field(default=None, ge=0)
    state: str = "IDLE"

