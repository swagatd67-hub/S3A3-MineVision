"""Integration Bridges for Digital Twin and Pipe Inspection Mapping Domains.

Note: Provides spatial coordinate association only. Full 3D defect projection, defect boundary estimation,
and defect spatial analysis belong to Phase 24 (Defect Projection).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mapping.models import PipeInspectionMap
from reconstruction.coordinates import cylindrical_to_cartesian
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


def associate_observations_with_3d_reconstruction(
    pipe_map: PipeInspectionMap,
    reconstruction: Reconstruction3DOutput,
) -> tuple[dict[str, Any], ...]:
    """Provide generic 3D spatial coordinate association for 2D pipe map observations.

    Full 3D defect projection and defect surface geometry are reserved for Phase 24.
    """
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
