"""Pydantic schemas for 3D Pipe Reconstruction Map API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BoundingBox2D(BaseModel):
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 1.0


class ReconstructionDefect(BaseModel):
    id: str
    class_code: str
    distance_m: float = Field(ge=0.0)
    clock_position: str = "12:00"
    clock_angle_deg: float = Field(default=0.0, ge=0.0, lt=360.0)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    frame_index: int | None = None
    box: BoundingBox2D | dict | None = None


class ReconstructionSection(BaseModel):
    section_index: int
    start_distance_m: float
    end_distance_m: float
    status: Literal["PENDING", "RECONSTRUCTED", "ANOMALOUS"] = "PENDING"
    outer_radius_mm: float = 300.0
    inner_radius_mm: float = 290.0
    defect_count: int = 0


class CenterlinePoint(BaseModel):
    x: float
    y: float
    z: float


class Reconstruction3DOutput(BaseModel):
    mission_id: str
    robot_id: str = "ROV-01"
    status: str = "INSPECTING"
    total_length_m: float = Field(default=50.0, ge=0.0)
    reconstructed_length_m: float = Field(default=0.0, ge=0.0)
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    diameter_mm: float = Field(default=600.0, ge=0.0)
    section_count: int = 10
    sections: list[ReconstructionSection] = Field(default_factory=list)
    centerline: list[CenterlinePoint] = Field(default_factory=list)
    defects: list[ReconstructionDefect] = Field(default_factory=list)
    generated_at: datetime
    version: str = "v1.0"
