"""3D Defect Projection Service for PipeVision Inspection Pipeline (Phase 24)."""

from __future__ import annotations

import math
import uuid

from backend.app.services.inspection.models import (
    CanonicalInspectionFrame,
    FusedInspectionObservation,
)
from reconstruction.coordinates import cylindrical_to_cartesian
from reconstruction.defect_models import (
    Defect3DFootprint,
    OrientationStatus,
    Projected3DDefect,
    ProjectionMethod,
    ProjectionStatus,
    Source2DGeometry,
)
from reconstruction.models import (
    CameraCalibration,
    PipeCenterlinePoint,
    Point3D,
    Reconstruction3DOutput,
    ReconstructionFrame,
    ScaleStatus,
)
from reconstruction.ray_caster import (
    camera_ray_to_world_ray,
    intersect_ray_with_pipe_cylinder,
    pixel_to_camera_ray,
)
from robot.localization.models import RobotPose


class Defect3DProjector:
    """Service for converting 2D perception defect observations into 3D pipe surface coordinates."""

    def __init__(self, default_pipe_diameter_mm: float = 300.0) -> None:
        self.default_pipe_diameter_mm = default_pipe_diameter_mm

    def project_observation(
        self,
        observation: FusedInspectionObservation,
        frame: ReconstructionFrame | CanonicalInspectionFrame | None = None,
        reconstruction: Reconstruction3DOutput | None = None,
        calibration: CameraCalibration | None = None,
        camera_offset_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Projected3DDefect:
        """Project a single 2D inspection observation into 3D pipe surface coordinates."""
        proj_id = f"proj_{uuid.uuid4().hex[:12]}"

        # 1. Parse 2D Source Geometry
        source_2d = self._parse_2d_geometry(observation, frame)
        if source_2d is None:
            return Projected3DDefect(
                projection_id=proj_id,
                observation_id=observation.observation_id,
                mission_id=observation.mission_id,
                class_code=observation.class_code,
                ai_confidence=observation.confidence,
                projection_confidence=0.0,
                source_2d_geometry=Source2DGeometry(center_pixel=(0.0, 0.0)),
                point_3d=None,
                longitudinal_distance_m=None,
                angular_position_rad=None,
                radial_position_m=None,
                quality_state=ProjectionStatus.INSUFFICIENT_DATA,
                scale_status=ScaleStatus.UNAVAILABLE,
                projection_method=ProjectionMethod.UNAVAILABLE,
                failure_reason="Invalid or missing 2D source geometry",
            )

        # 2. Extract RobotPose and distance
        pose = self._resolve_pose(observation, frame)
        dist_m = self._resolve_distance(observation, frame, pose)

        # 3. Check for Full Ray-Cylinder Intersection (Mode A)
        if (
            calibration is not None
            and pose is not None
            and reconstruction is not None
            and reconstruction.centerline is not None
            and len(reconstruction.centerline.points) > 0
        ):
            res_ray = self._project_via_ray_intersection(
                proj_id=proj_id,
                observation=observation,
                source_2d=source_2d,
                pose=pose,
                reconstruction=reconstruction,
                calibration=calibration,
                camera_offset_m=camera_offset_m,
            )
            if res_ray is not None:
                return res_ray

        # 4. Check for Centerline Cylindrical Mapping Fallback (Mode B)
        if dist_m is not None and dist_m >= 0.0:
            return self._project_via_cylindrical_mapping(
                proj_id=proj_id,
                observation=observation,
                source_2d=source_2d,
                dist_m=dist_m,
                reconstruction=reconstruction,
            )

        # 5. Missing Data / Failure Mode (Mode C)
        failure_reason = "Insufficient geometric context (missing pose, distance, or calibration)"
        if frame is not None and getattr(frame, "source", None) == "photo" and pose is None and dist_m is None:
            failure_reason = "Isolated single photo without 3D spatial reference or pose"

        return Projected3DDefect(
            projection_id=proj_id,
            observation_id=observation.observation_id,
            mission_id=observation.mission_id,
            class_code=observation.class_code,
            ai_confidence=observation.confidence,
            projection_confidence=0.0,
            source_2d_geometry=source_2d,
            point_3d=None,
            longitudinal_distance_m=None,
            angular_position_rad=None,
            radial_position_m=None,
            frame_id=getattr(frame, "frame_id", None),
            frame_index=observation.frame_index,
            timestamp=observation.timestamp,
            reconstruction_id=reconstruction.reconstruction_id if reconstruction else None,
            quality_state=ProjectionStatus.INSUFFICIENT_DATA,
            scale_status=ScaleStatus.UNAVAILABLE,
            projection_method=ProjectionMethod.UNAVAILABLE,
            failure_reason=failure_reason,
            provenance={
                "model_name": observation.model_name,
                "model_version": observation.model_version,
                "source_type": observation.source_type,
            },
        )

    def project_batch(
        self,
        observations: tuple[FusedInspectionObservation, ...],
        frames_by_index: dict[int, ReconstructionFrame | CanonicalInspectionFrame] | None = None,
        reconstruction: Reconstruction3DOutput | None = None,
        calibration: CameraCalibration | None = None,
    ) -> tuple[Projected3DDefect, ...]:
        """Project a batch of 2D inspection observations into 3D space."""
        frames_dict = frames_by_index or {}
        results: list[Projected3DDefect] = []

        for obs in observations:
            frame = frames_dict.get(obs.frame_index)
            proj = self.project_observation(
                observation=obs,
                frame=frame,
                reconstruction=reconstruction,
                calibration=calibration,
            )
            results.append(proj)

        return tuple(results)

    def _parse_2d_geometry(
        self,
        obs: FusedInspectionObservation,
        frame: ReconstructionFrame | CanonicalInspectionFrame | None,
    ) -> Source2DGeometry | None:
        """Extract 2D pixel coordinates and box dimensions from observation."""
        w = obs.image_width
        h = obs.image_height
        if w is None or h is None:
            if frame is not None and hasattr(frame, "metadata") and isinstance(frame.metadata, dict):
                w = frame.metadata.get("image_width", 1920)
                h = frame.metadata.get("image_height", 1080)
            else:
                w, h = 1920, 1080

        if obs.box is not None:
            center_x = (obs.box.x1 + obs.box.x2) / 2.0
            center_y = (obs.box.y1 + obs.box.y2) / 2.0
            return Source2DGeometry(
                center_pixel=(center_x, center_y),
                box=obs.box,
                image_width=w,
                image_height=h,
            )

        # Default center if no bounding box present
        return Source2DGeometry(
            center_pixel=(w / 2.0, h / 2.0),
            box=None,
            image_width=w,
            image_height=h,
        )

    def _resolve_pose(
        self,
        obs: FusedInspectionObservation,
        frame: ReconstructionFrame | CanonicalInspectionFrame | None,
    ) -> RobotPose | None:
        """Resolve RobotPose from observation or frame."""
        if obs.robot_pose is not None:
            return obs.robot_pose
        if frame is not None and hasattr(frame, "pose") and frame.pose is not None:
            return frame.pose
        return None

    def _resolve_distance(
        self,
        obs: FusedInspectionObservation,
        frame: ReconstructionFrame | CanonicalInspectionFrame | None,
        pose: RobotPose | None,
    ) -> float | None:
        """Resolve longitudinal distance in meters."""
        if obs.distance_m is not None:
            return obs.distance_m
        if obs.frame_distance_m is not None:
            return obs.frame_distance_m
        if obs.pose_distance_m is not None:
            return obs.pose_distance_m
        if frame is not None and hasattr(frame, "distance_m") and frame.distance_m is not None:
            return frame.distance_m
        if pose is not None:
            return pose.x
        return None

    def _project_via_ray_intersection(
        self,
        proj_id: str,
        observation: FusedInspectionObservation,
        source_2d: Source2DGeometry,
        pose: RobotPose,
        reconstruction: Reconstruction3DOutput,
        calibration: CameraCalibration,
        camera_offset_m: tuple[float, float, float],
    ) -> Projected3DDefect | None:
        """Perform analytical ray-cylinder intersection projection."""
        diameter_mm = (
            reconstruction.baseline_diameter_mm
            if reconstruction.baseline_diameter_mm is not None
            else self.default_pipe_diameter_mm
        )
        radius_m = (diameter_mm / 1000.0) / 2.0

        u, v = source_2d.center_pixel
        ray_cam = pixel_to_camera_ray(u, v, calibration)
        ray_orig_w, ray_dir_w = camera_ray_to_world_ray(ray_cam, pose, camera_offset_m)

        assert reconstruction.centerline is not None
        pt_int, s_m, theta_rad, normal = intersect_ray_with_pipe_cylinder(
            ray_origin=ray_orig_w,
            ray_direction=ray_dir_w,
            centerline=reconstruction.centerline,
            pipe_radius_m=radius_m,
        )

        if pt_int is None or s_m is None or theta_rad is None:
            return None

        # Compute Footprint from Bounding Box corners if available
        footprint: Defect3DFootprint | None = None
        if source_2d.box is not None:
            corners = [
                (source_2d.box.x1, source_2d.box.y1),
                (source_2d.box.x2, source_2d.box.y1),
                (source_2d.box.x2, source_2d.box.y2),
                (source_2d.box.x1, source_2d.box.y2),
            ]
            corner_pts: list[Point3D] = []
            s_vals: list[float] = []
            theta_vals: list[float] = []

            for cu, cv in corners:
                c_ray_cam = pixel_to_camera_ray(cu, cv, calibration)
                c_orig_w, c_dir_w = camera_ray_to_world_ray(c_ray_cam, pose, camera_offset_m)
                c_int, c_s, c_theta, _ = intersect_ray_with_pipe_cylinder(
                    ray_origin=c_orig_w,
                    ray_direction=c_dir_w,
                    centerline=reconstruction.centerline,
                    pipe_radius_m=radius_m,
                )
                if c_int is not None and c_s is not None and c_theta is not None:
                    corner_pts.append(c_int)
                    s_vals.append(c_s)
                    theta_vals.append(c_theta)

            if corner_pts:
                long_span = max(s_vals) - min(s_vals) if len(s_vals) > 1 else 0.0
                ang_span = max(theta_vals) - min(theta_vals) if len(theta_vals) > 1 else 0.0
                footprint = Defect3DFootprint(
                    center_3d=pt_int,
                    extent_type="PROJECTED_EXTENT_ESTIMATE",
                    longitudinal_span_m=long_span,
                    angular_span_rad=ang_span,
                    radial_deviation_mm=0.0,
                    boundary_points_3d=tuple(corner_pts),
                )

        scale_status = reconstruction.scale_status
        if calibration.calibration_status == "SYNTHETIC_TEST" and scale_status == ScaleStatus.UNAVAILABLE:
            scale_status = ScaleStatus.ESTABLISHED

        return Projected3DDefect(
            projection_id=proj_id,
            observation_id=observation.observation_id,
            mission_id=observation.mission_id,
            class_code=observation.class_code,
            ai_confidence=observation.confidence,
            projection_confidence=0.95 if reconstruction.quality_state.value == "VALID" else 0.75,
            source_2d_geometry=source_2d,
            point_3d=pt_int,
            longitudinal_distance_m=s_m,
            angular_position_rad=theta_rad,
            radial_position_m=radius_m,
            frame_index=observation.frame_index,
            timestamp=observation.timestamp,
            reconstruction_id=reconstruction.reconstruction_id,
            surface_normal=normal,
            orientation_status=OrientationStatus.AVAILABLE,
            quality_state=ProjectionStatus.VALID,
            scale_status=scale_status,
            projection_method=ProjectionMethod.RAY_CYLINDER_INTERSECTION,
            footprint_3d=footprint,
            uncertainty_info={
                "ray_intersection_valid": True,
                "reconstruction_quality": reconstruction.quality_state.value,
                "localization_quality": observation.localization_quality,
            },
            provenance={
                "model_name": observation.model_name,
                "model_version": observation.model_version,
                "source_type": observation.source_type,
            },
        )

    def _project_via_cylindrical_mapping(
        self,
        proj_id: str,
        observation: FusedInspectionObservation,
        source_2d: Source2DGeometry,
        dist_m: float,
        reconstruction: Reconstruction3DOutput | None,
    ) -> Projected3DDefect:
        """Perform fallback centerline cylindrical mapping projection."""
        diameter_mm = (
            reconstruction.baseline_diameter_mm
            if (reconstruction is not None and reconstruction.baseline_diameter_mm is not None)
            else self.default_pipe_diameter_mm
        )
        radius_m = (diameter_mm / 1000.0) / 2.0

        # Estimate clock angle theta from 2D pixel x coordinate
        u = source_2d.center_pixel[0]
        w = float(source_2d.image_width or 1920)
        norm_u = u / w if w > 0 else 0.5
        theta_rad = (norm_u * 2.0 * math.pi) % (2.0 * math.pi)

        # Centerline point lookup
        cl_pt = PipeCenterlinePoint(
            distance_m=dist_m,
            x=dist_m,
            y=0.0,
            z=0.0,
            heading_rad=0.0,
        )

        if reconstruction is not None and reconstruction.centerline and reconstruction.centerline.points:
            # Find closest centerline point
            min_d = float("inf")
            for pt in reconstruction.centerline.points:
                diff = abs(pt.distance_m - dist_m)
                if diff < min_d:
                    min_d = diff
                    cl_pt = pt

        pt_3d = cylindrical_to_cartesian(
            longitudinal_s_m=dist_m,
            angular_theta_rad=theta_rad,
            radius_r_m=radius_m,
            centerline_point=cl_pt,
        )

        scale_status = (
            reconstruction.scale_status
            if reconstruction is not None
            else ScaleStatus.UNAVAILABLE
        )

        return Projected3DDefect(
            projection_id=proj_id,
            observation_id=observation.observation_id,
            mission_id=observation.mission_id,
            class_code=observation.class_code,
            ai_confidence=observation.confidence,
            projection_confidence=0.60,
            source_2d_geometry=source_2d,
            point_3d=pt_3d,
            longitudinal_distance_m=dist_m,
            angular_position_rad=theta_rad,
            radial_position_m=radius_m,
            frame_index=observation.frame_index,
            timestamp=observation.timestamp,
            reconstruction_id=reconstruction.reconstruction_id if reconstruction else None,
            surface_normal=(pt_3d.nx or 0.0, pt_3d.ny or 0.0, pt_3d.nz or 1.0),
            orientation_status=OrientationStatus.ESTIMATED,
            quality_state=ProjectionStatus.DEGRADED,
            scale_status=scale_status,
            projection_method=ProjectionMethod.CENTERLINE_CYLINDRICAL_MAPPING,
            footprint_3d=Defect3DFootprint(
                center_3d=pt_3d,
                extent_type="PROJECTED_CENTER",
            ),
            uncertainty_info={
                "ray_intersection_valid": False,
                "note": "Mapped to cylindrical centerline position without full ray intersection",
            },
            provenance={
                "model_name": observation.model_name,
                "model_version": observation.model_version,
                "source_type": observation.source_type,
            },
        )
