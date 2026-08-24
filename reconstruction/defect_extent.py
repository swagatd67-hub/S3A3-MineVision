"""3D Defect Extent, Surface Metrics, and Spatial Relationship Calculations."""

from __future__ import annotations

import math
from collections.abc import Sequence

from reconstruction.analysis_models import (
    Defect3DMeasurement,
    MetricAvailabilityStatus,
    SpatialRelationship3D,
)
from reconstruction.calibration import CameraCalibration
from reconstruction.defect_models import Projected3DDefect, ProjectionStatus
from reconstruction.models import ScaleStatus


def compute_defect_extent(
    defect: Projected3DDefect,
    calibration: CameraCalibration | None = None,
    default_pipe_diameter_mm: float = 300.0,
) -> Defect3DMeasurement:
    """Compute physical 3D length, width, area, and angular extent for a projected defect."""
    if (
        defect.quality_state == ProjectionStatus.INSUFFICIENT_DATA
        or defect.longitudinal_distance_m is None
    ):
        return Defect3DMeasurement(
            observation_id=defect.observation_id,
            projection_id=defect.projection_id,
            class_code=defect.class_code,
            measurement_status=MetricAvailabilityStatus.UNAVAILABLE,
            length_m=None,
            width_m=None,
            area_m2=None,
            longitudinal_span_m=None,
            angular_span_rad=None,
            depth_m=None,
            depth_status=MetricAvailabilityStatus.UNAVAILABLE,
            confidence=defect.projection_confidence,
            notes=("Projection quality state is INSUFFICIENT_DATA; 3D extent unavailable.",),
        )

    pipe_radius_m = (default_pipe_diameter_mm / 1000.0) / 2.0
    notes: list[str] = []

    # 1. Evaluate scale status
    if defect.scale_status == ScaleStatus.ESTABLISHED:
        measurement_status = MetricAvailabilityStatus.ESTABLISHED
    elif defect.scale_status == ScaleStatus.ESTIMATED:
        measurement_status = MetricAvailabilityStatus.ESTIMATED
    else:
        measurement_status = MetricAvailabilityStatus.UNAVAILABLE

    # 2. Extract footprint dimensions if available
    fp = defect.footprint_3d
    if fp is not None:
        longitudinal_span_m = fp.longitudinal_span_m
        angular_span_rad = fp.angular_span_rad
        circumferential_span_m = angular_span_rad * pipe_radius_m

        length_m = max(longitudinal_span_m, circumferential_span_m)
        width_m = min(longitudinal_span_m, circumferential_span_m)
        area_m2 = longitudinal_span_m * circumferential_span_m
    else:
        # Point observation fallback (center pixel without explicit 2D box area)
        longitudinal_span_m = 0.0
        angular_span_rad = 0.0
        length_m = 0.0
        width_m = 0.0
        area_m2 = 0.0
        notes.append("No bounding footprint available; treated as point observation.")

    # 3. Depth analysis rule (Phase 4): Never infer physical depth from 2D pixel intensity
    # Only if radial position is explicitly measured differently from nominal radius is depth populated
    depth_m: float | None = None
    depth_status = MetricAvailabilityStatus.UNAVAILABLE
    if defect.radial_position_m is not None:
        delta_r = abs(defect.radial_position_m - pipe_radius_m)
        if delta_r > 1e-4 and measurement_status != MetricAvailabilityStatus.UNAVAILABLE:
            depth_m = delta_r
            depth_status = measurement_status
        else:
            depth_m = None
            depth_status = MetricAvailabilityStatus.UNAVAILABLE
            notes.append("No metric radial surface deformation observed at defect site; physical depth unavailable.")

    return Defect3DMeasurement(
        observation_id=defect.observation_id,
        projection_id=defect.projection_id,
        class_code=defect.class_code,
        measurement_status=measurement_status,
        length_m=length_m,
        width_m=width_m,
        area_m2=area_m2,
        longitudinal_span_m=longitudinal_span_m,
        angular_span_rad=angular_span_rad,
        depth_m=depth_m,
        depth_status=depth_status,
        confidence=defect.projection_confidence,
        notes=tuple(notes),
    )


def compute_spatial_relationships(
    defects: Sequence[Projected3DDefect],
    default_pipe_diameter_mm: float = 300.0,
    section_length_m: float = 1.0,
) -> list[SpatialRelationship3D]:
    """Compute pairwise surface-space distances and spatial relationships between projected defects."""
    valid_defects = [
        d
        for d in defects
        if d.quality_state != ProjectionStatus.INSUFFICIENT_DATA
        and d.longitudinal_distance_m is not None
        and d.angular_position_rad is not None
    ]

    relationships: list[SpatialRelationship3D] = []
    n = len(valid_defects)

    for i in range(n):
        d1 = valid_defects[i]
        assert d1.longitudinal_distance_m is not None
        assert d1.angular_position_rad is not None

        for j in range(i + 1, n):
            d2 = valid_defects[j]
            assert d2.longitudinal_distance_m is not None
            assert d2.angular_position_rad is not None

            # Longitudinal distance along pipe axis s
            longitudinal_dist_m = abs(d1.longitudinal_distance_m - d2.longitudinal_distance_m)

            # Angular separation theta (clock position difference)
            raw_diff = abs(d1.angular_position_rad - d2.angular_position_rad)
            angular_sep_rad = min(raw_diff, (2.0 * math.pi) - raw_diff)

            # 3D Euclidean distance
            euclidean_dist_3d: float | None = None
            euclidean_validity = MetricAvailabilityStatus.UNAVAILABLE

            if d1.point_3d is not None and d2.point_3d is not None:
                dx = d1.point_3d.x - d2.point_3d.x
                dy = d1.point_3d.y - d2.point_3d.y
                dz = d1.point_3d.z - d2.point_3d.z
                euclidean_dist_3d = math.sqrt(dx**2 + dy**2 + dz**2)
                euclidean_validity = (
                    MetricAvailabilityStatus.ESTABLISHED
                    if d1.scale_status == ScaleStatus.ESTABLISHED
                    else MetricAvailabilityStatus.ESTIMATED
                )

            is_same_sec = (
                int(d1.longitudinal_distance_m / section_length_m)
                == int(d2.longitudinal_distance_m / section_length_m)
            )

            relationships.append(
                SpatialRelationship3D(
                    source_projection_id=d1.projection_id,
                    target_projection_id=d2.projection_id,
                    longitudinal_distance_m=longitudinal_dist_m,
                    angular_separation_rad=angular_sep_rad,
                    euclidean_distance_3d_m=euclidean_dist_3d,
                    is_same_section=is_same_sec,
                    euclidean_validity=euclidean_validity,
                )
            )

    return relationships
