from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

MissionObjective = Literal["INSPECT", "INSPECT_AND_CLEAN", "INSPECT_SAMPLE"]
MissionStatus = Literal[
    "CREATED", "READY", "ACTIVE", "RUNNING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"
]


class MissionCreate(BaseModel):
    robot_id: str
    objective: MissionObjective = "INSPECT"
    notes: str | None = None


class Mission(BaseModel):
    mission_id: str
    robot_id: str
    objective: MissionObjective
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = None


class MissionProgressSchema(BaseModel):
    current_distance_m: float
    total_inspected_distance_m: float
    observation_count: int
    morphology_measurements_count: int
    cleaning_operations_count: int
    duration_sec: float | None = None


class MissionSnapshotSchema(BaseModel):
    mission_id: str
    robot_id: str
    objective: str
    status: str
    timestamps: dict[str, str | None]
    notes: str | None = None
    progress: MissionProgressSchema
    digital_twin: dict[str, Any] | None = None
