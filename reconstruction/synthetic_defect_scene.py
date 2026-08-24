"""Synthetic 3D Defect Scene Generator & Projection Accuracy Evaluator (Phase 16)."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from backend.app.services.inspection.models import (
    BoundingBox,
    FusedInspectionObservation,
)
from reconstruction.calibration import create_synthetic_test_calibration
from reconstruction.coordinates import cylindrical_to_cartesian
from reconstruction.defect_models import Projected3DDefect
from reconstruction.defect_projector import Defect3DProjector
from reconstruction.models import (
    PipeCenterlinePoint,
    Point3D,
    Reconstruction3DOutput,
    ReconstructionFrame,
)
from reconstruction.pipeline import Pipe3DReconstructionEngine
from reconstruction.synthetic_scene import SyntheticPipeSceneGenerator
from robot.localization.models import LocalizationQuality, RobotPose


class SyntheticDefectSceneGenerator:
    """Generates synthetic pipe scenes with known ground-truth 3D defect locations for algorithm validation."""

    def __init__(
        self,
        pipe_length_m: float = 10.0,
        pipe_diameter_mm: float = 300.0,
        frame_count: int = 21,
    ) -> None:
        self.pipe_length_m = pipe_length_m
        self.pipe_diameter_mm = pipe_diameter_mm
        self.frame_count = frame_count
        self.pipe_scene = SyntheticPipeSceneGenerator(
            pipe_length_m=pipe_length_m,
            pipe_diameter_mm=pipe_diameter_mm,
            frame_count=frame_count,
        )
        self.camera_calibration = create_synthetic_test_calibration()
        self.engine = Pipe3DReconstructionEngine(
            calibration=self.camera_calibration,
            default_pipe_diameter_mm=pipe_diameter_mm,
        )

    def generate_reconstruction_output(self) -> Reconstruction3DOutput:
        """Generate full synthetic 3D Pipe Reconstruction artifact."""
        frames = self.pipe_scene.generate_synthetic_frames()
        return self.engine.reconstruct(mission_id="synthetic_mission_001", frames=frames)

    def generate_synthetic_defect(
        self,
        gt_longitudinal_s_m: float = 8.0,
        gt_angular_theta_rad: float = 0.0,  # 12 o'clock top
        class_code: str = "CR",
        box_width_px: float = 100.0,
        box_height_px: float = 100.0,
    ) -> tuple[FusedInspectionObservation, Point3D, ReconstructionFrame]:
        """Generate a synthetic 2D observation and its true 3D ground-truth coordinate."""
        radius_m = (self.pipe_diameter_mm / 1000.0) / 2.0

        cl_pt = PipeCenterlinePoint(
            distance_m=gt_longitudinal_s_m,
            x=gt_longitudinal_s_m,
            y=0.0,
            z=0.0,
            heading_rad=0.0,
        )

        gt_3d_point = cylindrical_to_cartesian(
            longitudinal_s_m=gt_longitudinal_s_m,
            angular_theta_rad=gt_angular_theta_rad,
            radius_r_m=radius_m,
            centerline_point=cl_pt,
        )

        # Camera frame behind defect
        step = self.pipe_length_m / max(1, self.frame_count - 1)
        camera_dist = max(0.0, gt_longitudinal_s_m - 1.0)
        frame_idx = min(round(camera_dist / step), self.frame_count - 1)

        # Camera pose at frame
        pose = RobotPose(
            timestamp=datetime.now(timezone.utc),
            distance_m=camera_dist,
            x=camera_dist,
            y=0.0,
            heading_rad=0.0,
            heading_deg=0.0,
            quality=LocalizationQuality.TRACKING,
        )

        # Back-project 3D surface point to 2D image pixel (u, v)
        # Point in robot frame: x_r = gt_x - camera_dist, y_r = gt_y, z_r = gt_z
        x_r = gt_3d_point.x - camera_dist
        y_r = gt_3d_point.y
        z_r = gt_3d_point.z

        # Robot to camera frame: Z_c = x_r, X_c = -y_r, Y_c = -z_r
        z_c = x_r
        x_c = -y_r
        y_c = -z_r

        fx = self.camera_calibration.fx
        fy = self.camera_calibration.fy
        cx = self.camera_calibration.cx
        cy = self.camera_calibration.cy

        u_center = cx + (x_c / z_c) * fx if z_c > 0 else cx
        v_center = cy + (y_c / z_c) * fy if z_c > 0 else cy

        box = BoundingBox(
            x1=max(0.0, u_center - box_width_px / 2.0),
            y1=max(0.0, v_center - box_height_px / 2.0),
            x2=min(1920.0, u_center + box_width_px / 2.0),
            y2=min(1080.0, v_center + box_height_px / 2.0),
        )

        obs = FusedInspectionObservation(
            observation_id="synth_obs_01",
            mission_id="synth_mission_01",
            frame_index=frame_idx,
            timestamp=datetime.now(timezone.utc),
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
            distance_m=camera_dist,
            frame_distance_m=camera_dist,
            pose_distance_m=camera_dist,
            distance_conflict_m=0.0,
            robot_pose=pose,
            localization_quality="TRACKING",
            class_code=class_code,
            confidence=0.98,
            threshold=0.5,
            box=box,
            model_name="sewer_ml_synth",
            model_version="v1",
            source_type="photo",
            image_width=1920,
            image_height=1080,
        )

        rec_frame = ReconstructionFrame(
            frame_id=f"f_{frame_idx}",
            frame_index=frame_idx,
            timestamp=datetime.now(timezone.utc),
            image_path=f"/tmp/synth_frame_{frame_idx}.png",
            pose=pose,
            distance_m=camera_dist,
        )

        return (obs, gt_3d_point, rec_frame)

    def evaluate_projection_accuracy(
        self,
        gt_longitudinal_s_m: float = 8.0,
        gt_angular_theta_rad: float = 0.0,
    ) -> dict[str, float]:
        """SYNTHETIC ALGORITHM VALIDATION ONLY: Evaluate 3D defect projection error against known ground truth."""
        obs, gt_3d, rec_frame = self.generate_synthetic_defect(
            gt_longitudinal_s_m=gt_longitudinal_s_m,
            gt_angular_theta_rad=gt_angular_theta_rad,
        )

        reconstruction = self.generate_reconstruction_output()

        projector = Defect3DProjector(default_pipe_diameter_mm=self.pipe_diameter_mm)
        proj_result: Projected3DDefect = projector.project_observation(
            observation=obs,
            frame=rec_frame,
            reconstruction=reconstruction,
            calibration=self.camera_calibration,
        )

        assert proj_result.point_3d is not None
        assert proj_result.longitudinal_distance_m is not None

        dx = proj_result.point_3d.x - gt_3d.x
        dy = proj_result.point_3d.y - gt_3d.y
        dz = proj_result.point_3d.z - gt_3d.z
        error_3d_m = math.sqrt(dx**2 + dy**2 + dz**2)
        s_error_m = abs(proj_result.longitudinal_distance_m - gt_longitudinal_s_m)

        return {
            "synthetic_test_error_3d_m": round(error_3d_m, 6),
            "synthetic_test_s_error_m": round(s_error_m, 6),
        }
