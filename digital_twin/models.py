"""Domain Models for PipeVision Digital Twin Aggregation Layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from backend.app.services.inspection.models import FusedInspectionObservation
from cleaning.models import CleaningEffectiveness, CleaningOperation
from mapping.models import PipeInspectionMap
from morphology.models import MorphologySummaryReport
from robot.localization.models import RobotPose
from robot.telemetry.models import RobotTelemetry


class SynchronizationStatus(str, Enum):
    """Synchronization states for the Digital Twin representation."""

    INITIALIZING = "INITIALIZING"
    SYNCHRONIZED = "SYNCHRONIZED"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class DigitalTwinRobotState:
    """Virtual state representation of the physical crawler robot."""

    robot_id: str
    operational_state: str
    battery_percent: float | None
    distance_m: float
    body_diameter_mm: float | None
    pose: RobotPose | None
    telemetry_timestamp: datetime | None
    telemetry_freshness_sec: float | None
    telemetry: RobotTelemetry | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert robot twin state to standard dictionary format."""
        return {
            "robot_id": self.robot_id,
            "operational_state": self.operational_state,
            "battery_percent": (
                round(float(self.battery_percent), 1)
                if self.battery_percent is not None
                else None
            ),
            "distance_m": round(float(self.distance_m), 3),
            "body_diameter_mm": (
                round(float(self.body_diameter_mm), 2)
                if self.body_diameter_mm is not None
                else None
            ),
            "pose": (
                {
                    "x": round(float(self.pose.x), 3),
                    "y": round(float(self.pose.y), 3),
                    "heading_deg": round(float(self.pose.heading_deg), 2),
                    "quality": (
                        self.pose.quality.value
                        if hasattr(self.pose.quality, "value")
                        else str(self.pose.quality)
                    ),
                }
                if self.pose is not None
                else None
            ),
            "telemetry_timestamp": (
                self.telemetry_timestamp.isoformat()
                if self.telemetry_timestamp is not None
                else None
            ),
            "telemetry_freshness_sec": (
                round(float(self.telemetry_freshness_sec), 2)
                if self.telemetry_freshness_sec is not None
                else None
            ),
            "telemetry": (
                {
                    "robot_id": self.telemetry.robot_id,
                    "mission_id": self.telemetry.mission_id,
                    "timestamp": (
                        self.telemetry.timestamp.isoformat()
                        if self.telemetry.timestamp is not None
                        else None
                    ),
                    "battery_percent": self.telemetry.battery_percent,
                    "distance_m": self.telemetry.distance_m,
                    "body_diameter_mm": self.telemetry.body_diameter_mm,
                    "state": self.telemetry.state,
                }
                if self.telemetry is not None
                else None
            ),
        }


@dataclass(frozen=True)
class DigitalTwinMissionState:
    """Virtual representation of inspection mission context and spatial coverage."""

    mission_id: str
    current_distance_m: float
    total_inspected_distance_m: float
    start_distance_m: float | None
    end_distance_m: float | None
    observation_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert mission twin state to standard dictionary format."""
        return {
            "mission_id": self.mission_id,
            "current_distance_m": round(float(self.current_distance_m), 3),
            "total_inspected_distance_m": round(float(self.total_inspected_distance_m), 3),
            "start_distance_m": (
                round(float(self.start_distance_m), 3)
                if self.start_distance_m is not None
                else None
            ),
            "end_distance_m": (
                round(float(self.end_distance_m), 3)
                if self.end_distance_m is not None
                else None
            ),
            "observation_count": self.observation_count,
        }


@dataclass(frozen=True)
class DigitalTwinState:
    """Aggregated virtual snapshot of physical robot, mission, inspection, geometry, and cleaning state."""

    robot_id: str
    mission_id: str
    last_updated_at: datetime
    synchronization_status: str
    robot_state: DigitalTwinRobotState | None
    mission_state: DigitalTwinMissionState | None
    latest_observations: tuple[FusedInspectionObservation, ...] = ()
    inspection_map: PipeInspectionMap | None = None
    morphology_summary: MorphologySummaryReport | None = None
    active_cleaning_operation: CleaningOperation | None = None
    latest_cleaning_effectiveness: CleaningEffectiveness | None = None
    synchronization_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Export comprehensive JSON-serializable Digital Twin snapshot."""
        return {
            "system": {
                "robot_id": self.robot_id,
                "mission_id": self.mission_id,
                "last_updated_at": self.last_updated_at.isoformat(),
                "synchronization_status": self.synchronization_status,
                "synchronization_notes": list(self.synchronization_notes),
            },
            "robot": self.robot_state.to_dict() if self.robot_state is not None else None,
            "mission": self.mission_state.to_dict() if self.mission_state is not None else None,
            "latest_observations": [obs.to_dict() for obs in self.latest_observations],
            "inspection_map": self.inspection_map.to_dict() if self.inspection_map is not None else None,
            "morphology_summary": (
                self.morphology_summary.to_dict() if self.morphology_summary is not None else None
            ),
            "cleaning": {
                "active_operation": (
                    self.active_cleaning_operation.to_dict()
                    if self.active_cleaning_operation is not None
                    else None
                ),
                "latest_effectiveness": (
                    self.latest_cleaning_effectiveness.to_dict()
                    if self.latest_cleaning_effectiveness is not None
                    else None
                ),
            },
        }
