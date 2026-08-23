"""Application Models and Lifecycle State Definitions for Mission Orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class MissionLifecycleState(str, Enum):
    """Authoritative lifecycle state machine for inspection missions."""

    CREATED = "CREATED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    RUNNING = "RUNNING"  # Backwards compatibility alias for ACTIVE
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """Check whether a mission state string is terminal."""
        return state in {cls.COMPLETED.value, cls.FAILED.value, cls.CANCELLED.value}

    @classmethod
    def can_transition(cls, current_state: str, new_state: str) -> bool:
        """Validate whether state transition from current_state to new_state is allowed."""
        if current_state == new_state:
            return True

        if cls.is_terminal(current_state):
            return False

        allowed_map = {
            cls.CREATED.value: {cls.READY.value, cls.ACTIVE.value, cls.RUNNING.value, cls.CANCELLED.value},
            cls.READY.value: {cls.ACTIVE.value, cls.RUNNING.value, cls.PAUSED.value, cls.CANCELLED.value},
            cls.ACTIVE.value: {cls.PAUSED.value, cls.COMPLETED.value, cls.FAILED.value, cls.CANCELLED.value},
            cls.RUNNING.value: {cls.PAUSED.value, cls.COMPLETED.value, cls.FAILED.value, cls.CANCELLED.value},
            cls.PAUSED.value: {cls.ACTIVE.value, cls.RUNNING.value, cls.COMPLETED.value, cls.FAILED.value, cls.CANCELLED.value},
        }

        return new_state in allowed_map.get(current_state, set())


@dataclass(frozen=True)
class MissionProgressMetrics:
    """Quantitative progress metrics for an inspection mission."""

    current_distance_m: float
    total_inspected_distance_m: float
    observation_count: int
    morphology_measurements_count: int
    cleaning_operations_count: int
    duration_sec: float | None

    def to_dict(self) -> dict[str, Any]:
        """Convert progress metrics to dictionary format."""
        return {
            "current_distance_m": round(float(self.current_distance_m), 3),
            "total_inspected_distance_m": round(float(self.total_inspected_distance_m), 3),
            "observation_count": self.observation_count,
            "morphology_measurements_count": self.morphology_measurements_count,
            "cleaning_operations_count": self.cleaning_operations_count,
            "duration_sec": round(float(self.duration_sec), 2) if self.duration_sec is not None else None,
        }


@dataclass(frozen=True)
class MissionSnapshot:
    """Unified application-level snapshot combining domain states for consumption/frontend."""

    mission_id: str
    robot_id: str
    objective: str
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    notes: str | None
    progress: MissionProgressMetrics
    digital_twin: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        """Export comprehensive mission snapshot as dictionary."""
        return {
            "mission_id": self.mission_id,
            "robot_id": self.robot_id,
            "objective": self.objective,
            "status": self.status,
            "timestamps": {
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            },
            "notes": self.notes,
            "progress": self.progress.to_dict(),
            "digital_twin": self.digital_twin,
        }
