"""Data Contracts and Data Models for 3D Pipe Reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from robot.localization.models import RobotPose


class ReconstructionMethod(str, Enum):
    """Method utilized to compute 3D pipe reconstruction."""

    POSE_GUIDED = "POSE_GUIDED"
    VISUAL_ODOMETRY = "VISUAL_ODOMETRY"
    SFM = "SFM"
    GEOMETRIC_ESTIMATION = "GEOMETRIC_ESTIMATION"
    SINGLE_FRAME_FALLBACK = "SINGLE_FRAME_FALLBACK"


class ReconstructionQualityState(str, Enum):
    """Overall quality state of derived 3D reconstruction."""

    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class ScaleStatus(str, Enum):
    """Explicit metricity / scale availability state."""

    ESTABLISHED = "ESTABLISHED"  # Full metric scale from calibrated hardware pose / odometry
    ESTIMATED = "ESTIMATED"      # Estimated scale from baseline pipe morphology
    UNAVAILABLE = "UNAVAILABLE"  # Arbitrary/relative scale only


@dataclass(frozen=True)
class CameraCalibration:
    """Pinhole camera intrinsic and distortion parameters."""

    camera_id: str
    image_width: int
    image_height: int
    fx: float
    fy: float
    cx: float
    cy: float
    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    calibration_status: str = "UNCALIBRATED"  # CALIBRATED, SYNTHETIC_TEST, UNCALIBRATED
    calibration_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "image_dimensions": {
                "width": self.image_width,
                "height": self.image_height,
            },
            "intrinsics": {
                "fx": round(float(self.fx), 3),
                "fy": round(float(self.fy), 3),
                "cx": round(float(self.cx), 3),
                "cy": round(float(self.cy), 3),
            },
            "distortion": {
                "k1": round(float(self.k1), 5),
                "k2": round(float(self.k2), 5),
                "p1": round(float(self.p1), 5),
                "p2": round(float(self.p2), 5),
            },
            "calibration_status": self.calibration_status,
            "calibration_version": self.calibration_version,
        }


@dataclass(frozen=True)
class ReconstructionFrame:
    """Canonical frame input for 3D reconstruction pipeline."""

    frame_id: str
    frame_index: int
    timestamp: datetime | None = None
    image_path: str | None = None
    image_bytes: bytes | None = None
    pose: RobotPose | None = None
    distance_m: float | None = None
    source: str = "photo"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp.isoformat() if self.timestamp is not None else None,
            "distance_m": round(float(self.distance_m), 3) if self.distance_m is not None else None,
            "has_image": bool(self.image_path or self.image_bytes),
            "pose": (
                {
                    "x": round(float(self.pose.x), 3),
                    "y": round(float(self.pose.y), 3),
                    "heading_deg": round(float(self.pose.heading_deg), 2),
                    "quality": str(self.pose.quality),
                }
                if self.pose is not None
                else None
            ),
            "source": self.source,
        }


@dataclass(frozen=True)
class ReconstructionJob:
    """Metadata context describing a 3D reconstruction execution request."""

    job_id: str
    mission_id: str
    source_type: str
    frame_count: int
    calibration_id: str | None
    has_pose: bool
    has_distance: bool
    method: ReconstructionMethod

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "mission_id": self.mission_id,
            "source_type": self.source_type,
            "frame_count": self.frame_count,
            "calibration_id": self.calibration_id,
            "has_pose": self.has_pose,
            "has_distance": self.has_distance,
            "method": self.method.value,
        }


@dataclass(frozen=True)
class Point3D:
    """Point representation in Cartesian 3D space (units: meters)."""

    x: float
    y: float
    z: float
    nx: float | None = None
    ny: float | None = None
    nz: float | None = None
    r: int | None = None
    g: int | None = None
    b: int | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "x": round(float(self.x), 4),
            "y": round(float(self.y), 4),
            "z": round(float(self.z), 4),
        }
        if self.nx is not None and self.ny is not None and self.nz is not None:
            res["normal"] = {
                "nx": round(float(self.nx), 4),
                "ny": round(float(self.ny), 4),
                "nz": round(float(self.nz), 4),
            }
        if self.r is not None and self.g is not None and self.b is not None:
            res["color_rgb"] = [int(self.r), int(self.g), int(self.b)]
        return res


@dataclass(frozen=True)
class PipeCenterlinePoint:
    """3D point along the pipe longitudinal trajectory (units: meters, radians)."""

    distance_m: float
    x: float
    y: float
    z: float
    heading_rad: float = 0.0
    pitch_rad: float = 0.0
    roll_rad: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "distance_m": round(float(self.distance_m), 3),
            "position": {
                "x": round(float(self.x), 4),
                "y": round(float(self.y), 4),
                "z": round(float(self.z), 4),
            },
            "orientation_rad": {
                "heading": round(float(self.heading_rad), 4),
                "pitch": round(float(self.pitch_rad), 4),
                "roll": round(float(self.roll_rad), 4),
            },
        }


@dataclass(frozen=True)
class PipeCenterline:
    """Structured longitudinal centerline profile of the pipe."""

    points: tuple[PipeCenterlinePoint, ...]
    total_length_m: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_length_m": round(float(self.total_length_m), 3),
            "point_count": len(self.points),
            "points": [p.to_dict() for p in self.points],
        }


@dataclass(frozen=True)
class PipeSurfacePoint:
    """Cylindrical surface coordinate (longitudinal s, angular theta, radial offset delta_r)."""

    longitudinal_distance_m: float
    angular_position_rad: float
    radial_offset_mm: float
    radius_mm: float
    point_3d: Point3D

    def to_dict(self) -> dict[str, Any]:
        return {
            "longitudinal_distance_m": round(float(self.longitudinal_distance_m), 3),
            "angular_position_rad": round(float(self.angular_position_rad), 4),
            "radial_offset_mm": round(float(self.radial_offset_mm), 2),
            "radius_mm": round(float(self.radius_mm), 2),
            "point_3d": self.point_3d.to_dict(),
        }


@dataclass(frozen=True)
class Reconstruction3DOutput:
    """Comprehensive machine-readable 3D Pipe Reconstruction artifact."""

    reconstruction_id: str
    mission_id: str
    method: ReconstructionMethod
    quality_state: ReconstructionQualityState
    scale_status: ScaleStatus
    units: str = "meters"
    coordinate_frame: str = "CANONICAL_PIPE_3D"
    calibration: CameraCalibration | None = None
    frame_count: int = 0
    centerline: PipeCenterline | None = None
    surface_points: tuple[PipeSurfacePoint, ...] = ()
    points_3d: tuple[Point3D, ...] = ()
    baseline_diameter_mm: float | None = None
    quality_metrics: dict[str, Any] = field(default_factory=dict)
    quality_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "reconstruction_id": self.reconstruction_id,
                "mission_id": self.mission_id,
                "method": self.method.value,
                "quality_state": self.quality_state.value,
                "scale_status": self.scale_status.value,
                "units": self.units,
                "coordinate_frame": self.coordinate_frame,
                "frame_count": self.frame_count,
                "baseline_diameter_mm": (
                    round(float(self.baseline_diameter_mm), 2)
                    if self.baseline_diameter_mm is not None
                    else None
                ),
            },
            "calibration": self.calibration.to_dict() if self.calibration is not None else None,
            "centerline": self.centerline.to_dict() if self.centerline is not None else None,
            "surface_points_summary": {
                "count": len(self.surface_points),
                "samples": [sp.to_dict() for sp in self.surface_points[:50]],  # Subsample for JSON header
            },
            "points_3d_count": len(self.points_3d),
            "quality_metrics": self.quality_metrics,
            "quality_notes": list(self.quality_notes),
        }
