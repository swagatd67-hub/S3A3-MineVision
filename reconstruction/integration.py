"""Integration Bridges for Digital Twin and Pipe Inspection Mapping Domains (Phases 23, 24 & 25)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mapping.models import PipeInspectionMap
from reconstruction.analysis_models import Pipe3DAnalysisReport
from reconstruction.coordinates import cylindrical_to_cartesian
from reconstruction.defect_models import Grouped3DDefect, Projected3DDefect
from reconstruction.models import Reconstruction3DOutput

if TYPE_CHECKING:
    from digital_twin.models import DigitalTwinState


def associate_reconstruction_with_digital_twin(
    digital_twin_state: DigitalTwinState | Any,
    reconstruction: Reconstruction3DOutput,
) -> dict[str, Any]:
    """Expose 3D Pipe Reconstruction as a derived spatial artifact within Digital Twin state dictionary."""
    base_dict: dict[str, Any]
    if hasattr(digital_twin_state, "to_dict"):
        base_dict = digital_twin_state.to_dict()
    elif isinstance(digital_twin_state, dict):
        base_dict = dict(digital_twin_state)
    else:
        base_dict = {"digital_twin_state": str(digital_twin_state)}

    base_dict["reconstruction_3d"] = reconstruction.to_dict()
    return base_dict


def associate_projected_defects_with_digital_twin(
    digital_twin_state: DigitalTwinState | Any,
    projected_defects: tuple[Projected3DDefect, ...],
    grouped_defects: tuple[Grouped3DDefect, ...] = (),
) -> dict[str, Any]:
    """Attach Phase 24 projected 3D defect information as an additive spatial layer in Digital Twin state dictionary."""
    base_dict: dict[str, Any]
    if hasattr(digital_twin_state, "to_dict"):
        base_dict = digital_twin_state.to_dict()
    elif isinstance(digital_twin_state, dict):
        base_dict = dict(digital_twin_state)
    else:
        base_dict = {"digital_twin_state": str(digital_twin_state)}

    base_dict["projected_defects_3d"] = {
        "count": len(projected_defects),
        "defects": [d.to_dict() for d in projected_defects],
        "grouped_clusters_count": len(grouped_defects),
        "grouped_clusters": [g.to_dict() for g in grouped_defects],
    }
    return base_dict


def associate_advanced_3d_analysis_with_digital_twin(
    digital_twin_state: DigitalTwinState | Any,
    analysis_report: Pipe3DAnalysisReport,
) -> dict[str, Any]:
    """Expose Phase 25 Advanced 3D Condition Analysis as additive derived data in Digital Twin state dictionary."""
    base_dict: dict[str, Any]
    if hasattr(digital_twin_state, "to_dict"):
        base_dict = digital_twin_state.to_dict()
    elif isinstance(digital_twin_state, dict):
        base_dict = dict(digital_twin_state)
    else:
        base_dict = {"digital_twin_state": str(digital_twin_state)}

    base_dict["advanced_3d_analysis"] = analysis_report.to_dict()
    return base_dict


def associate_observations_with_3d_reconstruction(
    pipe_map: PipeInspectionMap,
    reconstruction: Reconstruction3DOutput,
) -> tuple[dict[str, Any], ...]:
    """Provide generic 3D spatial coordinate association for 2D pipe map observations."""
    if not reconstruction.centerline or not reconstruction.centerline.points:
        return ()

    mapped_3d_obs: list[dict[str, Any]] = []

    for obs in pipe_map.observations:
        # Match observation distance against reconstruction centerline
        dist = obs.distance_m
        # Estimate angular clock position if bounding box is available (default 12 o'clock / 0 rad)
        theta_rad = 0.0
        if obs.box is not None:
            # Estimate clock angle from bounding box center x coordinate
            box_center_x = (obs.box.x1 + obs.box.x2) / 2.0
            # Map normalized width [0, 1] or [0, 1920] to [0, 2*pi]
            if box_center_x > 1.0:
                norm_x = box_center_x / 1920.0
            else:
                norm_x = box_center_x
            theta_rad = norm_x * 2.0 * 3.1415926535

        # Find closest centerline point
        closest_centerline = reconstruction.centerline.points[0]
        min_diff = float("inf")
        for cl_pt in reconstruction.centerline.points:
            diff = abs(cl_pt.distance_m - dist)
            if diff < min_diff:
                min_diff = diff
                closest_centerline = cl_pt

        radius_m = ((reconstruction.baseline_diameter_mm or 300.0) / 1000.0) / 2.0
        pt_3d = cylindrical_to_cartesian(
            longitudinal_s_m=dist,
            angular_theta_rad=theta_rad,
            radius_r_m=radius_m,
            centerline_point=closest_centerline,
        )

        mapped_3d_obs.append(
            {
                "observation_id": obs.observation_id,
                "class_code": obs.class_code,
                "confidence": obs.confidence,
                "distance_m": dist,
                "angular_position_rad": round(theta_rad, 4),
                "point_3d": pt_3d.to_dict(),
            }
        )

    return tuple(mapped_3d_obs)


def associate_projected_defects_with_mapping(
    pipe_map: PipeInspectionMap,
    projected_defects: tuple[Projected3DDefect, ...],
) -> tuple[dict[str, Any], ...]:
    """Expose optional 3D defect association for PipeInspectionMap observations without altering 2D mapping semantics."""
    defects_by_obs_id = {d.observation_id: d for d in projected_defects}
    linked_observations: list[dict[str, Any]] = []

    for obs in pipe_map.observations:
        obs_dict = obs.to_dict()
        proj = defects_by_obs_id.get(obs.observation_id)
        if proj is not None and proj.point_3d is not None:
            obs_dict["projected_3d"] = proj.to_dict()
        else:
            obs_dict["projected_3d"] = None
        linked_observations.append(obs_dict)

    return tuple(linked_observations)


def associate_advanced_3d_analysis_with_mapping(
    pipe_map: PipeInspectionMap,
    analysis_report: Pipe3DAnalysisReport,
) -> dict[str, Any]:
    """Expose section-level and summary 3D condition analytics to existing mapping as an additive layer."""
    map_dict = pipe_map.to_dict()
    map_dict["advanced_3d_analysis"] = {
        "analysis_version": analysis_report.analysis_version,
        "scale_status": analysis_report.scale_status.value,
        "overall_condition_score": analysis_report.summary.overall_condition_score,
        "mean_defect_density_per_m": analysis_report.summary.mean_defect_density_per_m,
        "sections": [s.to_dict() for s in analysis_report.sections],
    }
    return map_dict
