"""Domain Models for Pipe Cleaning Operations & Effectiveness Analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from cleaning.exceptions import InvalidOperationError


class CleaningStatus(str, Enum):
    """Finite states for a cleaning operation."""

    REQUESTED = "REQUESTED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class CleaningMode(str, Enum):
    """Supported physical cleaning operational modes."""

    FLUSH = "FLUSH"
    SCRUB = "SCRUB"
    CUTTER = "CUTTER"
    VACUUM = "VACUUM"
    DEFAULT = "DEFAULT"


@dataclass(frozen=True)
class CleaningOperation:
    """Immutable representation of a sewer pipe cleaning operation."""

    operation_id: str
    mission_id: str
    mode: str
    status: str
    start_timestamp: datetime | None
    end_timestamp: datetime | None
    start_distance_m: float | None
    end_distance_m: float | None
    source: str = "operator"
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Validate model invariants."""
        if not self.operation_id.strip():
            raise InvalidOperationError("operation_id cannot be empty.")
        if not self.mission_id.strip():
            raise InvalidOperationError("mission_id cannot be empty.")

        if (
            self.start_timestamp is not None
            and self.end_timestamp is not None
            and self.end_timestamp < self.start_timestamp
        ):
            raise InvalidOperationError(
                f"end_timestamp ({self.end_timestamp.isoformat()}) cannot precede "
                f"start_timestamp ({self.start_timestamp.isoformat()})."
            )

        if (
            self.start_distance_m is not None
            and self.end_distance_m is not None
            and self.end_distance_m < self.start_distance_m
        ):
            raise InvalidOperationError(
                f"end_distance_m ({self.end_distance_m}m) cannot be less than "
                f"start_distance_m ({self.start_distance_m}m)."
            )

        if self.start_distance_m is not None and self.start_distance_m < 0.0:
            raise InvalidOperationError("start_distance_m cannot be negative.")

        if self.end_distance_m is not None and self.end_distance_m < 0.0:
            raise InvalidOperationError("end_distance_m cannot be negative.")

    def with_status(
        self,
        new_status: str,
        end_timestamp: datetime | None = None,
        end_distance_m: float | None = None,
    ) -> CleaningOperation:
        """Create a new CleaningOperation instance with updated status and end parameters."""
        resolved_end_ts = end_timestamp if end_timestamp is not None else self.end_timestamp
        resolved_end_dist = end_distance_m if end_distance_m is not None else self.end_distance_m

        return CleaningOperation(
            operation_id=self.operation_id,
            mission_id=self.mission_id,
            mode=self.mode,
            status=new_status,
            start_timestamp=self.start_timestamp,
            end_timestamp=resolved_end_ts,
            start_distance_m=self.start_distance_m,
            end_distance_m=resolved_end_dist,
            source=self.source,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert cleaning operation to standard dictionary format."""
        return {
            "operation_id": self.operation_id,
            "mission_id": self.mission_id,
            "mode": self.mode,
            "status": self.status,
            "start_timestamp": (
                self.start_timestamp.isoformat() if self.start_timestamp is not None else None
            ),
            "end_timestamp": (
                self.end_timestamp.isoformat() if self.end_timestamp is not None else None
            ),
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
            "source": self.source,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CleaningEffectiveness:
    """Quantitative comparison of pipe condition before and after a cleaning operation."""

    operation_id: str
    mission_id: str
    start_distance_m: float
    end_distance_m: float
    before_observation_count: int
    after_observation_count: int
    before_defect_classes: tuple[str, ...]
    after_defect_classes: tuple[str, ...]
    resolved_defect_classes: tuple[str, ...]
    persistent_defect_classes: tuple[str, ...]
    new_defect_classes: tuple[str, ...]
    defect_count_change: int
    measurable_change: bool
    confidence: str
    is_effective: bool | None
    unavailable_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert effectiveness analysis result to standard dictionary format."""
        return {
            "operation_id": self.operation_id,
            "mission_id": self.mission_id,
            "region": {
                "start_distance_m": round(float(self.start_distance_m), 3),
                "end_distance_m": round(float(self.end_distance_m), 3),
            },
            "comparison": {
                "before_observation_count": self.before_observation_count,
                "after_observation_count": self.after_observation_count,
                "before_defect_classes": list(self.before_defect_classes),
                "after_defect_classes": list(self.after_defect_classes),
                "resolved_defect_classes": list(self.resolved_defect_classes),
                "persistent_defect_classes": list(self.persistent_defect_classes),
                "new_defect_classes": list(self.new_defect_classes),
                "defect_count_change": self.defect_count_change,
            },
            "assessment": {
                "measurable_change": self.measurable_change,
                "confidence": self.confidence,
                "is_effective": self.is_effective,
                "unavailable_reasons": list(self.unavailable_reasons),
            },
        }
