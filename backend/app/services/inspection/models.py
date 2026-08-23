"""Domain Models for Inspection Observation Fusion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from robot.localization.models import RobotPose


@dataclass(frozen=True)
class BoundingBox:
    """2D Pixel Bounding Box for object detections (e.g. YOLO)."""

    x1: float
    y1: float
    x2: float
    y2: float

    def to_dict(self) -> dict[str, float]:
        return {
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
            "x2": round(self.x2, 2),
            "y2": round(self.y2, 2),
        }


@dataclass(frozen=True)
class RawPerceptionItem:
    """Normalized internal perception item prior to spatial/temporal fusion."""

    class_code: str
    confidence: float
    model_name: str
    model_version: str = "v1"
    threshold: float | None = None
    box: BoundingBox | None = None
    source_type: str = "unknown"
    detected: bool = True


@dataclass(frozen=True)
class InspectionFrameMetadata:
    """Metadata context for an inspected video frame."""

    mission_id: str
    frame_index: int
    timestamp: str | datetime | None = None
    distance_m: float | None = None
    image_width: int | None = None
    image_height: int | None = None


@dataclass(frozen=True)
class FusedInspectionObservation:
    """Immutable localized inspection observation linking perception to spatial/temporal context."""

    observation_id: str
    mission_id: str
    frame_index: int
    timestamp: datetime | None
    timestamp_iso: str | None
    distance_m: float | None
    frame_distance_m: float | None
    pose_distance_m: float | None
    distance_conflict_m: float | None
    robot_pose: RobotPose | None
    localization_quality: str
    class_code: str
    confidence: float
    threshold: float | None
    box: BoundingBox | None
    model_name: str
    model_version: str
    source_type: str
    image_width: int | None = None
    image_height: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert fused observation to standard dictionary representation."""
        return {
            "observation_id": self.observation_id,
            "mission_id": self.mission_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp_iso,
            "distance_m": round(self.distance_m, 3) if self.distance_m is not None else None,
            "frame_distance_m": round(self.frame_distance_m, 3) if self.frame_distance_m is not None else None,
            "pose_distance_m": round(self.pose_distance_m, 3) if self.pose_distance_m is not None else None,
            "distance_conflict_m": round(self.distance_conflict_m, 3) if self.distance_conflict_m is not None else None,
            "localization_quality": self.localization_quality,
            "robot_pose": (
                {
                    "x": round(self.robot_pose.x, 3),
                    "y": round(self.robot_pose.y, 3),
                    "heading_deg": round(self.robot_pose.heading_deg, 2),
                    "quality": self.robot_pose.quality.value if hasattr(self.robot_pose.quality, "value") else str(self.robot_pose.quality),
                }
                if self.robot_pose is not None
                else None
            ),
            "class_code": self.class_code,
            "confidence": round(self.confidence, 4),
            "threshold": round(self.threshold, 4) if self.threshold is not None else None,
            "box": self.box.to_dict() if self.box is not None else None,
            "provenance": {
                "model_name": self.model_name,
                "model_version": self.model_version,
                "source_type": self.source_type,
            },
            "image_dimensions": {
                "width": self.image_width,
                "height": self.image_height,
            },
        }


@dataclass(frozen=True)
class CanonicalInspectionFrame:
    """Canonical robot-agnostic inspection frame contract for PipeVision ingestion."""

    mission_id: str
    robot_id: str | None = None
    frame_id: str | None = None
    camera_id: str | None = None
    timestamp: str | datetime | None = None
    source: str = "photo"  # 'photo', 'video', 'live'
    frame_index: int = 0
    image_bytes: bytes | None = None
    image_path: str | None = None
    distance_m: float | None = None
    pose: RobotPose | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class SingleIngestionResult:
    """Normalized ingestion outcome for a single photo / frame."""

    mission_id: str
    frame_id: str
    frame_index: int
    timestamp_iso: str | None
    source: str
    distance_m: float | None
    frame_path: str | None
    observations: list[FusedInspectionObservation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "frame_id": self.frame_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp_iso,
            "source": self.source,
            "distance_m": round(self.distance_m, 3) if self.distance_m is not None else None,
            "frame_path": self.frame_path,
            "observations_count": len(self.observations),
            "observations": [obs.to_dict() for obs in self.observations],
        }


@dataclass(frozen=True)
class BatchIngestionResult:
    """Ingestion outcome summary for a batch of photos / frames."""

    mission_id: str
    total_submitted: int
    total_succeeded: int
    total_failed: int
    results: list[SingleIngestionResult]
    failures: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "total_submitted": self.total_submitted,
            "total_succeeded": self.total_succeeded,
            "total_failed": self.total_failed,
            "results": [r.to_dict() for r in self.results],
            "failures": self.failures,
        }
