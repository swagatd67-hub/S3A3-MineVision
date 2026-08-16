from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class IMUData(BaseModel):
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float


class PressureData(BaseModel):
    body_kpa: Optional[float] = None
    front_anchor_kpa: Optional[float] = None
    rear_anchor_kpa: Optional[float] = None


class WaterQualityData(BaseModel):
    temperature_c: Optional[float] = None
    ph: Optional[float] = None
    conductivity_ms_cm: Optional[float] = None
    turbidity_ntu: Optional[float] = None


class TelemetryPacket(BaseModel):
    robot_id: str
    mission_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    battery_percent: Optional[float] = Field(default=None, ge=0, le=100)
    imu: Optional[IMUData] = None
    pressure: Optional[PressureData] = None
    water: Optional[WaterQualityData] = None
    distance_m: Optional[float] = Field(default=None, ge=0)
    body_diameter_mm: Optional[float] = Field(default=None, ge=0)
    state: str = "IDLE"
