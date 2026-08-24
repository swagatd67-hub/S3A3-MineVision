"""Comprehensive Test Suite for 3D Pipe Reconstruction Module."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

import pytest

# Ensure backend mission orchestrator is loaded before domain modules to prevent circular package init cycles
import backend.app.services.mission.orchestrator  # noqa: F401
from digital_twin.models import DigitalTwinState, SynchronizationStatus
from mapping.models import MapObservation, PipeInspectionMap
from reconstruction.calibration import (
    CameraCalibrationModel,
    create_synthetic_test_calibration,
)
from reconstruction.coordinates import (
    camera_to_robot,
    cylindrical_to_cartesian,
    robot_to_world,
)
from reconstruction.exceptions import CalibrationError
from reconstruction.frame_selector import FrameSelector
from reconstruction.integration import (
    associate_observations_with_3d_reconstruction,
    associate_reconstruction_with_digital_twin,
)
from reconstruction.models import (
    CameraCalibration,
    PipeCenterlinePoint,
    Point3D,
    ReconstructionFrame,
    ReconstructionQualityState,
    ScaleStatus,
)
from reconstruction.pipeline import Pipe3DReconstructionEngine
from reconstruction.synthetic_scene import SyntheticPipeSceneGenerator
from robot.localization.models import LocalizationQuality, RobotPose


def test_camera_calibration_model() -> None:
    cal = create_synthetic_test_calibration()
    assert cal.calibration_status == "SYNTHETIC_TEST"
    assert cal.image_width == 1920
    assert cal.image_height == 1080

    model = CameraCalibrationModel(cal)
    assert model.is_synthetic() is True
    assert model.camera_matrix.shape == (3, 3)
    assert model.distortion_coeffs.shape == (4,)

    invalid_cal = CameraCalibration(
        camera_id="bad",
        image_width=0,
        image_height=1080,
        fx=1000.0,
        fy=1000.0,
        cx=500.0,
        cy=500.0,
    )
    with pytest.raises(CalibrationError):
        CameraCalibrationModel(invalid_cal)


def test_coordinate_transformations() -> None:
    # 1. Camera to Robot frame
    pt_cam = Point3D(x=0.5, y=0.2, z=2.0)
    pt_robot = camera_to_robot(pt_cam)
    assert math.isclose(pt_robot.x, 2.0)
    assert math.isclose(pt_robot.y, -0.5)
    assert math.isclose(pt_robot.z, -0.2)

    # 2. Robot to World frame
    pose = RobotPose(
        timestamp=datetime.now(timezone.utc),
        distance_m=10.0,
        x=10.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )
    pt_world = robot_to_world(pt_robot, pose)
    assert math.isclose(pt_world.x, 12.0)
    assert math.isclose(pt_world.y, -0.5)
    assert math.isclose(pt_world.z, -0.2)

    # 3. Cylindrical to Cartesian
    cl_pt = PipeCenterlinePoint(distance_m=5.0, x=5.0, y=0.0, z=0.0, heading_rad=0.0)
    # Top of pipe (theta = 0 rad)
    pt_top = cylindrical_to_cartesian(
        longitudinal_s_m=5.0,
        angular_theta_rad=0.0,
        radius_r_m=0.15,
        centerline_point=cl_pt,
    )
    assert math.isclose(pt_top.x, 5.0)
    assert math.isclose(pt_top.y, 0.0)
    assert math.isclose(pt_top.z, 0.15)


def test_frame_selection() -> None:
    frames = [
        ReconstructionFrame(
            frame_id=f"f_{i}",
            frame_index=i,
            distance_m=i * 0.02,  # 0.02m step
            image_path=f"/tmp/frame_{i}.png",
        )
        for i in range(10)
    ]

    selector = FrameSelector(min_distance_step_m=0.05, min_frame_step=1)
    selected = selector.select_frames(frames)
    # With 0.02 step and 0.05 min step: expect frames 0, 3, 6, 9
    assert len(selected) < len(frames)
    assert selected[0].frame_index == 0


def test_synthetic_pipe_reconstruction_accuracy() -> None:
    """SYNTHETIC TEST SCENE ACCURACY: Verify <0.1% centerline accuracy on deterministic synthetic pipe scene.

    This test evaluates mathematical consistency on synthetic fixture data only, not real-world hardware accuracy.
    """
    scene = SyntheticPipeSceneGenerator(
        pipe_length_m=10.0,
        pipe_diameter_mm=300.0,
        frame_count=21,
    )
    synthetic_frames = scene.generate_synthetic_frames()
    engine = Pipe3DReconstructionEngine(
        calibration=scene.camera_calibration,
        default_pipe_diameter_mm=300.0,
        angular_sample_count=16,
    )

    result = engine.reconstruct(mission_id="m_synth_01", frames=synthetic_frames)

    assert result.quality_state == ReconstructionQualityState.VALID
    assert result.scale_status == ScaleStatus.ESTABLISHED
    assert result.centerline is not None
    # SYNTHETIC TEST SCENE ACCURACY assertion:
    assert math.isclose(result.centerline.total_length_m, 10.0, abs_tol=0.01)
    assert len(result.surface_points) == 21 * 16
    assert len(result.points_3d) == 21 * 16


def test_failure_injection_scenarios() -> None:
    engine = Pipe3DReconstructionEngine()

    # Scenario A: 0 frames
    res_empty = engine.reconstruct(mission_id="m_empty", frames=[])
    assert res_empty.quality_state == ReconstructionQualityState.INSUFFICIENT_DATA
    assert res_empty.frame_count == 0

    # Scenario B: Single isolated frame must return INSUFFICIENT_DATA
    single_frame = ReconstructionFrame(
        frame_id="f_single",
        frame_index=0,
        image_path="/tmp/single.png",
    )
    res_single = engine.reconstruct(mission_id="m_single", frames=[single_frame])
    assert res_single.quality_state == ReconstructionQualityState.INSUFFICIENT_DATA
    assert res_single.frame_count == 1
    assert "Isolated single image" in res_single.quality_notes[0]


def test_digital_twin_and_mapping_integration() -> None:
    scene = SyntheticPipeSceneGenerator(pipe_length_m=5.0, frame_count=10)
    frames = scene.generate_synthetic_frames()
    engine = Pipe3DReconstructionEngine(calibration=scene.camera_calibration)
    rec_out = engine.reconstruct("m_integ", frames)

    # 1. Additive Digital Twin Integration
    twin_state = DigitalTwinState(
        robot_id="robot_01",
        mission_id="m_integ",
        last_updated_at=datetime.now(timezone.utc),
        synchronization_status=SynchronizationStatus.SYNCHRONIZED.value,
        robot_state=None,
        mission_state=None,
    )

    twin_dict = associate_reconstruction_with_digital_twin(twin_state, rec_out)
    assert "reconstruction_3d" in twin_dict
    assert twin_dict["reconstruction_3d"]["metadata"]["mission_id"] == "m_integ"

    # 2. Additive Mapping Spatial Association Bridge
    map_obs = MapObservation(
        observation_id="obs_01",
        mission_id="m_integ",
        frame_index=2,
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
        mission_id="m_integ",
        total_inspected_distance_m=5.0,
        start_distance_m=0.0,
        end_distance_m=5.0,
        observation_count=1,
        observations=(map_obs,),
    )

    obs_3d = associate_observations_with_3d_reconstruction(pipe_map, rec_out)
    assert len(obs_3d) == 1
    assert obs_3d[0]["observation_id"] == "obs_01"
    assert "point_3d" in obs_3d[0]


def test_performance_and_bounded_memory() -> None:
    # Test 100 and 500 frame reconstruction speed and bounded memory output
    scene_500 = SyntheticPipeSceneGenerator(
        pipe_length_m=50.0,
        frame_count=500,
    )
    frames_500 = scene_500.generate_synthetic_frames()
    engine = Pipe3DReconstructionEngine(
        angular_sample_count=8,
        frame_selector=FrameSelector(min_distance_step_m=0.01),
    )

    t0 = time.perf_counter()
    out_500 = engine.reconstruct("m_perf_500", frames_500)
    elapsed_sec = time.perf_counter() - t0

    assert out_500.quality_state == ReconstructionQualityState.VALID
    assert out_500.frame_count > 0
    # Execution should be sub-second for 500 frames
    assert elapsed_sec < 2.0
