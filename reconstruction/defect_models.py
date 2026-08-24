"""Data Models for 3D Defect Projection & Analysis (Phase 24)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from backend.app.services.inspection.models import BoundingBox
from reconstruction.models import Point3D, ScaleStatus


class ProjectionStatus(str, Enum):
    """Quality / outcome status of 3D defect projection."""

    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class ProjectionMethod(str, Enum):
    """Geometric method used to derive 3D defect position."""

    RAY_CYLINDER_INTERSECTION = "RAY_CYLINDER_INTERSECTION"
    CENTERLINE_CYLINDRICAL_MAPPING = "CENTERLINE_CYLINDRICAL_MAPPING"
    POSE_GEOMETRIC_PROJECTION = "POSE_GEOMETRIC_PROJECTION"
    SINGLE_FRAME_APPROXIMATION = "SINGLE_FRAME_APPROXIMATION"
    UNAVAILABLE = "UNAVAILABLE"


class OrientationStatus(str, Enum):
    """Availability state of surface orientation / normal vectors."""

    AVAILABLE = "AVAILABLE"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class Source2DGeometry:
    """Representation of 2D defect source geometry from perception detector."""

    center_pixel: tuple[float, float]
    box: BoundingBox | None = None
    contour_pixels: tuple[tuple[float, float], ...] = ()
    image_width: int | None = None
    image_height: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "center_pixel": [round(self.center_pixel[0], 2), round(self.center_pixel[1], 2)],
            "box": self.box.to_dict() if self.box is not None else None,
            "has_contour": len(self.contour_pixels) > 0,
            "contour_point_count": len(self.contour_pixels),
            "image_dimensions": {
                "width": self.image_width,
                "height": self.image_height,
            },
        }


@dataclass(frozen=True)
class Defect3DFootprint:
    """3D spatial extent and boundary footprint of projected defect."""

    center_3d: Point3D
    extent_type: str  # PROJECTED_CENTER, PROJECTED_EXTENT_ESTIMATE, SAMPLED_CONTOUR_3D
    longitudinal_span_m: float = 0.0
    angular_span_rad: float = 0.0
    radial_deviation_mm: float = 0.0
    boundary_points_3d: tuple[Point3D, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "center_3d": self.center_3d.to_dict(),
            "extent_type": self.extent_type,
            "longitudinal_span_m": round(float(self.longitudinal_span_m), 4),
            "angular_span_rad": round(float(self.angular_span_rad), 4),
            "radial_deviation_mm": round(float(self.radial_deviation_mm), 2),
            "boundary_points_count": len(self.boundary_points_3d),
            "boundary_points": [pt.to_dict() for pt in self.boundary_points_3d[:20]],
        }


@dataclass(frozen=True)
class Projected3DDefect:
    """Comprehensive machine-readable contract for a 3D projected pipe defect."""

    projection_id: str
    observation_id: str
    mission_id: str
    class_code: str
    ai_confidence: float
    projection_confidence: float
    source_2d_geometry: Source2DGeometry
    point_3d: Point3D | None
    longitudinal_distance_m: float | None
    angular_position_rad: float | None
    radial_position_m: float | None
    frame_id: str | None = None
    frame_index: int | None = None
    timestamp: datetime | None = None
    reconstruction_id: str | None = None
    surface_normal: tuple[float, float, float] | None = None
    orientation_status: OrientationStatus = OrientationStatus.UNAVAILABLE
    quality_state: ProjectionStatus = ProjectionStatus.INSUFFICIENT_DATA
    scale_status: ScaleStatus = ScaleStatus.UNAVAILABLE
    projection_method: ProjectionMethod = ProjectionMethod.UNAVAILABLE
    footprint_3d: Defect3DFootprint | None = None
    failure_reason: str | None = None
    uncertainty_info: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection_id": self.projection_id,
            "observation_id": self.observation_id,
            "mission_id": self.mission_id,
            "frame_id": self.frame_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp.isoformat() if self.timestamp is not None else None,
            "reconstruction_id": self.reconstruction_id,
            "defect_class": self.class_code,
            "ai_confidence": round(float(self.ai_confidence), 4),
            "projection_confidence": round(float(self.projection_confidence), 4),
            "source_2d_geometry": self.source_2d_geometry.to_dict(),
            "projected_3d_coordinate": (
                self.point_3d.to_dict() if self.point_3d is not None else None
            ),
            "pipe_cylindrical_coordinates": {
                "longitudinal_distance_m": (
                    round(float(self.longitudinal_distance_m), 3)
                    if self.longitudinal_distance_m is not None
                    else None
                ),
                "angular_position_rad": (
                    round(float(self.angular_position_rad), 4)
                    if self.angular_position_rad is not None
                    else None
                ),
                "radial_position_m": (
                    round(float(self.radial_position_m), 4)
                    if self.radial_position_m is not None
                    else None
                ),
            },
            "surface_normal": (
                {
                    "nx": round(float(self.surface_normal[0]), 4),
                    "ny": round(float(self.surface_normal[1]), 4),
                    "nz": round(float(self.surface_normal[2]), 4),
                }
                if self.surface_normal is not None
                else None
            ),
            "orientation_status": self.orientation_status.value,
            "quality_state": self.quality_state.value,
            "scale_status": self.scale_status.value,
            "projection_method": self.projection_method.value,
            "footprint_3d": self.footprint_3d.to_dict() if self.footprint_3d is not None else None,
            "failure_reason": self.failure_reason,
            "uncertainty_info": self.uncertainty_info,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class Grouped3DDefect:
    """Clustered representation of the same physical defect observed across multiple frames."""

    cluster_id: str
    mission_id: str
    class_code: str
    primary_projection_id: str
    member_projection_ids: tuple[str, ...]
    frame_ids: tuple[str, ...]
    mean_longitudinal_distance_m: float
    mean_angular_position_rad: float
    mean_point_3d: Point3D
    observation_count: int
    max_ai_confidence: float
    overall_quality_state: ProjectionStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "mission_id": self.mission_id,
            "class_code": self.class_code,
            "primary_projection_id": self.primary_projection_id,
            "member_projection_ids": list(self.member_projection_ids),
            "frame_ids": list(self.frame_ids),
            "mean_longitudinal_distance_m": round(float(self.mean_longitudinal_distance_m), 3),
            "mean_angular_position_rad": round(float(self.mean_angular_position_rad), 4),
            "mean_point_3d": self.mean_point_3d.to_dict(),
            "observation_count": self.observation_count,
            "max_ai_confidence": round(float(self.max_ai_confidence), 4),
            "overall_quality_state": self.overall_quality_state.value,
        }
