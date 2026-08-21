"""Domain Models for Pipe Morphology & Geometry Analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MorphologyCalibration:
    """Camera and sensor calibration parameters for pipe geometry derivation."""

    baseline_pipe_diameter_mm: float | None = None
    focal_length_px: float | None = None
    pixel_per_mm: float | None = None
    calibration_mode: str = "UNCALIBRATED"

    def is_calibrated(self) -> bool:
        """Check if calibration provides a valid conversion scale."""
        return (
            self.calibration_mode != "UNCALIBRATED"
            and self.pixel_per_mm is not None
            and float(self.pixel_per_mm) > 0.0
        )


@dataclass(frozen=True)
class PipeMorphologyObservation:
    """Dimensional and morphological feature snapshot along the pipe."""

    observation_id: str
    mission_id: str
    frame_index: int
    timestamp: datetime | None
    timestamp_iso: str | None
    distance_m: float
    robot_body_diameter_mm: float | None
    measured_pipe_diameter_mm: float | None
    estimated_pipe_diameter_mm: float | None
    effective_pipe_diameter_mm: float | None
    baseline_pipe_diameter_mm: float | None
    deformation_percent: float | None
    pixel_span_px: float | None
    quality: str
    source: str
    calibration_mode: str = "UNCALIBRATED"

    def to_dict(self) -> dict[str, Any]:
        """Convert morphology observation to standard dictionary format."""
        return {
            "observation_id": self.observation_id,
            "mission_id": self.mission_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp_iso,
            "distance_m": round(float(self.distance_m), 3),
            "robot_body_diameter_mm": (
                round(float(self.robot_body_diameter_mm), 2)
                if self.robot_body_diameter_mm is not None
                else None
            ),
            "measured_pipe_diameter_mm": (
                round(float(self.measured_pipe_diameter_mm), 2)
                if self.measured_pipe_diameter_mm is not None
                else None
            ),
            "estimated_pipe_diameter_mm": (
                round(float(self.estimated_pipe_diameter_mm), 2)
                if self.estimated_pipe_diameter_mm is not None
                else None
            ),
            "effective_pipe_diameter_mm": (
                round(float(self.effective_pipe_diameter_mm), 2)
                if self.effective_pipe_diameter_mm is not None
                else None
            ),
            "baseline_pipe_diameter_mm": (
                round(float(self.baseline_pipe_diameter_mm), 2)
                if self.baseline_pipe_diameter_mm is not None
                else None
            ),
            "deformation_percent": (
                round(float(self.deformation_percent), 2)
                if self.deformation_percent is not None
                else None
            ),
            "pixel_span_px": (
                round(float(self.pixel_span_px), 1)
                if self.pixel_span_px is not None
                else None
            ),
            "quality": self.quality,
            "provenance": {
                "source": self.source,
                "calibration_mode": self.calibration_mode,
            },
        }


@dataclass(frozen=True)
class MorphologySummaryReport:
    """Summary metrics of pipe morphology across an entire mission or segment."""

    mission_id: str
    total_observations: int
    measured_count: int
    estimated_count: int
    unavailable_count: int
    invalid_count: int
    min_observed_diameter_mm: float | None
    max_observed_diameter_mm: float | None
    mean_observed_diameter_mm: float | None
    max_deformation_percent: float | None
    mean_deformation_percent: float | None
    observations: tuple[PipeMorphologyObservation, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert morphology summary report to dictionary format."""
        return {
            "mission_id": self.mission_id,
            "metrics": {
                "total_observations": self.total_observations,
                "measured_count": self.measured_count,
                "estimated_count": self.estimated_count,
                "unavailable_count": self.unavailable_count,
                "invalid_count": self.invalid_count,
                "min_observed_diameter_mm": (
                    round(float(self.min_observed_diameter_mm), 2)
                    if self.min_observed_diameter_mm is not None
                    else None
                ),
                "max_observed_diameter_mm": (
                    round(float(self.max_observed_diameter_mm), 2)
                    if self.max_observed_diameter_mm is not None
                    else None
                ),
                "mean_observed_diameter_mm": (
                    round(float(self.mean_observed_diameter_mm), 2)
                    if self.mean_observed_diameter_mm is not None
                    else None
                ),
                "max_deformation_percent": (
                    round(float(self.max_deformation_percent), 2)
                    if self.max_deformation_percent is not None
                    else None
                ),
                "mean_deformation_percent": (
                    round(float(self.mean_deformation_percent), 2)
                    if self.mean_deformation_percent is not None
                    else None
                ),
            },
            "observations": [obs.to_dict() for obs in self.observations],
        }
