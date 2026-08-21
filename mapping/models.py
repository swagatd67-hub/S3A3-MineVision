"""Domain Models for Pipe Inspection Mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.app.services.inspection.models import (
    BoundingBox,
    FusedInspectionObservation,
)


@dataclass(frozen=True)
class MapObservation:
    """Spatially located inspection observation feature on the pipe map."""

    observation_id: str
    mission_id: str
    frame_index: int
    timestamp: datetime | None
    timestamp_iso: str | None
    distance_m: float
    x: float
    y: float
    heading_rad: float | None
    heading_deg: float | None
    class_code: str
    confidence: float
    threshold: float | None
    box: BoundingBox | None
    localization_quality: str
    model_name: str
    model_version: str
    source_type: str

    @classmethod
    def from_fused_observation(
        cls, obs: FusedInspectionObservation
    ) -> MapObservation:
        """Create a MapObservation from a FusedInspectionObservation."""
        dist = obs.distance_m if obs.distance_m is not None else 0.0
        heading_rad = (
            obs.robot_pose.heading_rad if obs.robot_pose is not None else None
        )
        heading_deg = (
            obs.robot_pose.heading_deg if obs.robot_pose is not None else None
        )

        return cls(
            observation_id=obs.observation_id,
            mission_id=obs.mission_id,
            frame_index=obs.frame_index,
            timestamp=obs.timestamp,
            timestamp_iso=obs.timestamp_iso,
            distance_m=dist,
            x=dist,
            y=0.0,
            heading_rad=heading_rad,
            heading_deg=heading_deg,
            class_code=obs.class_code,
            confidence=obs.confidence,
            threshold=obs.threshold,
            box=obs.box,
            localization_quality=obs.localization_quality,
            model_name=obs.model_name,
            model_version=obs.model_version,
            source_type=obs.source_type,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert map observation to standard dictionary format."""
        return {
            "observation_id": self.observation_id,
            "mission_id": self.mission_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp_iso,
            "distance_m": round(self.distance_m, 3),
            "coordinates": {
                "x": round(self.x, 3),
                "y": round(self.y, 3),
            },
            "heading_deg": (
                round(self.heading_deg, 2) if self.heading_deg is not None else None
            ),
            "class_code": self.class_code,
            "confidence": round(self.confidence, 4),
            "threshold": (
                round(self.threshold, 4) if self.threshold is not None else None
            ),
            "box": self.box.to_dict() if self.box is not None else None,
            "localization_quality": self.localization_quality,
            "provenance": {
                "model_name": self.model_name,
                "model_version": self.model_version,
                "source_type": self.source_type,
            },
        }


@dataclass(frozen=True)
class MapTrajectoryPoint:
    """Robot trajectory snapshot point along the pipe map."""

    timestamp: datetime | None
    distance_m: float
    x: float
    y: float
    heading_rad: float | None
    heading_deg: float | None
    quality: str


@dataclass(frozen=True)
class PipeInspectionMap:
    """Immutable spatial map of pipe inspection observations along longitudinal distance."""

    mission_id: str
    total_inspected_distance_m: float
    start_distance_m: float | None
    end_distance_m: float | None
    observation_count: int
    observations: tuple[MapObservation, ...]
    trajectory_summary: tuple[MapTrajectoryPoint, ...] = ()

    def max_distance(self) -> float | None:
        """Return maximum inspected distance along pipe."""
        return self.end_distance_m

    def observations_at_distance(
        self,
        distance_m: float,
        tolerance_m: float = 0.1,
        include_invalid: bool = False,
    ) -> tuple[MapObservation, ...]:
        """Query map observations within tolerance of target distance."""
        return tuple(
            obs
            for obs in self.observations
            if abs(obs.distance_m - distance_m) <= tolerance_m
            and (include_invalid or obs.localization_quality != "INVALID")
        )

    def observations_between(
        self,
        start_m: float,
        end_m: float,
        include_invalid: bool = False,
    ) -> tuple[MapObservation, ...]:
        """Query map observations within a longitudinal range [start_m, end_m]."""
        low = min(start_m, end_m)
        high = max(start_m, end_m)
        return tuple(
            obs
            for obs in self.observations
            if low <= obs.distance_m <= high
            and (include_invalid or obs.localization_quality != "INVALID")
        )

    def defects_by_class(
        self,
        class_code: str,
        include_invalid: bool = False,
    ) -> tuple[MapObservation, ...]:
        """Query map observations matching defect class_code."""
        target = class_code.strip().lower()
        return tuple(
            obs
            for obs in self.observations
            if obs.class_code.strip().lower() == target
            and (include_invalid or obs.localization_quality != "INVALID")
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert entire inspection map to dictionary format."""
        return {
            "mission_id": self.mission_id,
            "summary": {
                "total_inspected_distance_m": round(
                    self.total_inspected_distance_m, 3
                ),
                "start_distance_m": (
                    round(self.start_distance_m, 3)
                    if self.start_distance_m is not None
                    else None
                ),
                "end_distance_m": (
                    round(self.end_distance_m, 3)
                    if self.end_distance_m is not None
                    else None
                ),
                "observation_count": self.observation_count,
            },
            "observations": [obs.to_dict() for obs in self.observations],
        }
