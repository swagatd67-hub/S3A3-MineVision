"""Comprehensive Test Suite for Phase 24 3D Defect Projection & Analysis."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

# Ensure backend orchestrator is loaded before domain modules to prevent circular package init cycles
import backend.app.services.mission.orchestrator  # noqa: F401
from backend.app.services.inspection.models import (
    BoundingBox,
    CanonicalInspectionFrame,
    FusedInspectionObservation,
)
from digital_twin.models import DigitalTwinState, SynchronizationStatus
from mapping.models import MapObservation, PipeInspectionMap
from reconstruction.calibration import create_synthetic_test_calibration
from reconstruction.defect_clustering import MultiFrameDefectAssociator
from reconstruction.defect_models import (
    Projected3DDefect,
    ProjectionStatus,
    Source2DGeometry,
)
from reconstruction.defect_projector import Defect3DProjector
from reconstruction.integration import (
    associate_projected_defects_with_digital_twin,
    associate_projected_defects_with_mapping,
)
from reconstruction.models import Point3D, ScaleStatus
from reconstruction.ray_caster import (
    camera_ray_to_world_ray,
    intersect_ray_with_pipe_cylinder,
    pixel_to_camera_ray,
)
from reconstruction.synthetic_defect_scene import SyntheticDefectSceneGenerator
from robot.localization.models import LocalizationQuality, RobotPose


def test_pixel_to_ray_conversion() -> None:
    cal = create_synthetic_test_calibration()
    # Center pixel (960, 540) should map to optical axis ray (0, 0, 1) in camera frame
    ray_center = pixel_to_camera_ray(960.0, 540.0, cal)
    assert math.isclose(ray_center[0], 0.0, abs_tol=1e-4)
    assert math.isclose(ray_center[1], 0.0, abs_tol=1e-4)
    assert math.isclose(ray_center[2], 1.0, abs_tol=1e-4)

    # Offset pixel to the right
    ray_right = pixel_to_camera_ray(1440.0, 540.0, cal)
    assert ray_right[0] > 0.0
    assert math.isclose(ray_right[1], 0.0, abs_tol=1e-4)


def test_camera_world_transforms() -> None:
    pose = RobotPose(
        timestamp=datetime.now(timezone.utc),
        distance_m=10.0,
        x=10.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )
    ray_cam = (0.0, 0.0, 1.0)  # Optical axis forward
    ray_orig_w, ray_dir_w = camera_ray_to_world_ray(ray_cam, pose)

    # Camera origin at pose x=10.0
    assert math.isclose(ray_orig_w.x, 10.0, abs_tol=1e-3)
    # Camera +Z_c maps to Robot/World +X_w forward direction (1, 0, 0)
    assert math.isclose(ray_dir_w.x, 1.0, abs_tol=1e-3)
    assert math.isclose(ray_dir_w.y, 0.0, abs_tol=1e-3)
    assert math.isclose(ray_dir_w.z, 0.0, abs_tol=1e-3)


def test_cylindrical_ray_intersection() -> None:
    scene_gen = SyntheticDefectSceneGenerator(pipe_length_m=10.0, pipe_diameter_mm=300.0)
    reconstruction = scene_gen.generate_reconstruction_output()

    ray_orig = Point3D(x=5.0, y=0.0, z=0.0)
    ray_dir = Point3D(x=0.0, y=0.0, z=1.0)  # Ray pointing straight up towards top of pipe

    assert reconstruction.centerline is not None
    pt_int, s_m, theta_rad, normal = intersect_ray_with_pipe_cylinder(
        ray_origin=ray_orig,
        ray_direction=ray_dir,
        centerline=reconstruction.centerline,
        pipe_radius_m=0.15,
    )

    assert pt_int is not None
    assert s_m is not None
    assert theta_rad is not None
    assert math.isclose(pt_int.z, 0.15, abs_tol=1e-3)
    assert math.isclose(s_m, 5.0, abs_tol=1e-3)
    assert math.isclose(theta_rad, 0.0, abs_tol=1e-3)
    assert normal is not None
    # Inward normal points down (nz = -1)
    assert math.isclose(normal[2], -1.0, abs_tol=1e-3)


def test_synthetic_defect_ground_truth() -> None:
    """SYNTHETIC ALGORITHM VALIDATION ONLY: Test 3D defect projection against synthetic ground truth."""
    scene_gen = SyntheticDefectSceneGenerator(pipe_length_m=10.0, pipe_diameter_mm=300.0)
    eval_res = scene_gen.evaluate_projection_accuracy(
        gt_longitudinal_s_m=8.0,
        gt_angular_theta_rad=0.0,
    )

    assert eval_res["synthetic_test_s_error_m"] < 0.05
    assert eval_res["synthetic_test_error_3d_m"] < 0.10


def test_missing_data_failure_modes() -> None:
    projector = Defect3DProjector()
    obs = FusedInspectionObservation(
        observation_id="obs_bad",
        mission_id="m_test",
        frame_index=0,
        timestamp=datetime.now(timezone.utc),
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        distance_m=None,
        frame_distance_m=None,
        pose_distance_m=None,
        distance_conflict_m=None,
        robot_pose=None,
        localization_quality="UNKNOWN",
        class_code="CR",
        confidence=0.9,
        threshold=0.5,
        box=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0),
        model_name="sewer_ml",
        model_version="v1",
        source_type="photo",
        image_width=1920,
        image_height=1080,
    )

    # Isolated photo with missing pose, distance, and calibration
    proj = projector.project_observation(
        observation=obs,
        frame=CanonicalInspectionFrame(mission_id="m_test", source="photo", frame_index=0),
        reconstruction=None,
        calibration=None,
    )

    assert proj.quality_state == ProjectionStatus.INSUFFICIENT_DATA
    assert proj.point_3d is None
    assert proj.scale_status == ScaleStatus.UNAVAILABLE
    assert "Isolated single photo" in (proj.failure_reason or "")


def test_multi_frame_clustering() -> None:
    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    # 3 projections of the same crack across consecutive frames
    p1 = Projected3DDefect(
        projection_id="p1",
        observation_id="obs_1",
        mission_id="m_cluster",
        class_code="CR",
        ai_confidence=0.90,
        projection_confidence=0.95,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=5.0, y=0.0, z=0.15),
        longitudinal_distance_m=5.0,
        angular_position_rad=0.1,
        radial_position_m=0.15,
        frame_id="f1",
        quality_state=ProjectionStatus.VALID,
    )
    p2 = Projected3DDefect(
        projection_id="p2",
        observation_id="obs_2",
        mission_id="m_cluster",
        class_code="CR",
        ai_confidence=0.94,
        projection_confidence=0.95,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=5.05, y=0.01, z=0.15),
        longitudinal_distance_m=5.05,
        angular_position_rad=0.12,
        radial_position_m=0.15,
        frame_id="f2",
        quality_state=ProjectionStatus.VALID,
    )
    # Different defect 3 meters further down
    p3 = Projected3DDefect(
        projection_id="p3",
        observation_id="obs_3",
        mission_id="m_cluster",
        class_code="CR",
        ai_confidence=0.88,
        projection_confidence=0.95,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=8.0, y=0.0, z=0.15),
        longitudinal_distance_m=8.0,
        angular_position_rad=0.1,
        radial_position_m=0.15,
        frame_id="f3",
        quality_state=ProjectionStatus.VALID,
    )

    associator = MultiFrameDefectAssociator(longitudinal_threshold_m=0.30)
    clusters = associator.cluster_projections((p1, p2, p3))

    assert len(clusters) == 2
    assert clusters[0].observation_count == 2
    assert "p1" in clusters[0].member_projection_ids
    assert "p2" in clusters[0].member_projection_ids
    assert clusters[1].observation_count == 1
    assert "p3" in clusters[1].member_projection_ids


def test_digital_twin_and_mapping_bridges() -> None:
    twin_state = DigitalTwinState(
        robot_id="r1",
        mission_id="m1",
        last_updated_at=datetime.now(timezone.utc),
        synchronization_status=SynchronizationStatus.SYNCHRONIZED.value,
        robot_state=None,
        mission_state=None,
    )

    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    proj = Projected3DDefect(
        projection_id="p1",
        observation_id="obs_1",
        mission_id="m1",
        class_code="CR",
        ai_confidence=0.95,
        projection_confidence=0.90,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=2.0, y=0.0, z=0.15),
        longitudinal_distance_m=2.0,
        angular_position_rad=0.0,
        radial_position_m=0.15,
        quality_state=ProjectionStatus.VALID,
    )

    # 1. Digital Twin additive bridge
    twin_dict = associate_projected_defects_with_digital_twin(twin_state, (proj,))
    assert "projected_defects_3d" in twin_dict
    assert twin_dict["projected_defects_3d"]["count"] == 1

    # 2. Mapping additive bridge
    map_obs = MapObservation(
        observation_id="obs_1",
        mission_id="m1",
        frame_index=0,
        timestamp=datetime.now(timezone.utc),
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        distance_m=2.0,
        x=2.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        class_code="CR",
        confidence=0.95,
        threshold=0.5,
        box=None,
        localization_quality="TRACKING",
        model_name="sewer_ml",
        model_version="v1",
        source_type="photo",
    )
    pipe_map = PipeInspectionMap(
        mission_id="m1",
        total_inspected_distance_m=5.0,
        start_distance_m=0.0,
        end_distance_m=5.0,
        observation_count=1,
        observations=(map_obs,),
    )

    linked_map = associate_projected_defects_with_mapping(pipe_map, (proj,))
    assert len(linked_map) == 1
    assert linked_map[0]["projected_3d"] is not None
    assert linked_map[0]["projected_3d"]["projection_id"] == "p1"


def test_performance_and_bounded_memory() -> None:
    projector = Defect3DProjector()
    observations: list[FusedInspectionObservation] = []

    for i in range(500):
        obs = FusedInspectionObservation(
            observation_id=f"obs_perf_{i}",
            mission_id="m_perf",
            frame_index=i,
            timestamp=datetime.now(timezone.utc),
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
            distance_m=i * 0.1,
            frame_distance_m=i * 0.1,
            pose_distance_m=i * 0.1,
            distance_conflict_m=0.0,
            robot_pose=None,
            localization_quality="TRACKING",
            class_code="CR",
            confidence=0.92,
            threshold=0.5,
            box=BoundingBox(x1=50.0, y1=50.0, x2=150.0, y2=150.0),
            model_name="sewer_ml",
            model_version="v1",
            source_type="photo",
            image_width=1920,
            image_height=1080,
        )
        observations.append(obs)

    t0 = time.perf_counter()
    projections = projector.project_batch(tuple(observations))
    elapsed_sec = time.perf_counter() - t0

    assert len(projections) == 500
    # 500 projections should execute sub-second (< 1.5s)
    assert elapsed_sec < 1.5
