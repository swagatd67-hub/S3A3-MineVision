"""Comprehensive Unit & Integration Tests for PipeVision Digital Twin Domain."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.inspection import (
    InspectionFrameMetadata,
    RawPerceptionItem,
    fuse_observations,
)
from cleaning import (
    CleaningMode,
    CleaningOperation,
    CleaningStatus,
    evaluate_cleaning_effectiveness,
)
from digital_twin import (
    DigitalTwinSynchronizer,
    MissionMismatchError,
    StaleUpdateError,
    SynchronizationStatus,
)
from mapping import build_inspection_map
from morphology import (
    MorphologyCalibration,
    analyze_morphology,
)
from robot.localization import LocalizationQuality, RobotPose
from robot.telemetry import RobotTelemetry


def test_initial_digital_twin_state() -> None:
    sync = DigitalTwinSynchronizer(robot_id="PV-01", mission_id="MIS-INIT")
    state = sync.snapshot()

    assert state.robot_id == "PV-01"
    assert state.mission_id == "MIS-INIT"
    assert state.synchronization_status == SynchronizationStatus.INITIALIZING.value
    assert state.robot_state is None
    assert state.mission_state is not None
    assert state.mission_state.mission_id == "MIS-INIT"
    assert len(state.latest_observations) == 0


def test_telemetry_update_and_monotonicity() -> None:
    sync = DigitalTwinSynchronizer()
    now = datetime.now(timezone.utc)

    telem1 = RobotTelemetry(
        robot_id="PV-01",
        mission_id="MIS-TELEM",
        timestamp=now,
        battery_percent=85.0,
        distance_m=10.0,
        body_diameter_mm=220.0,
        state="MOVING",
    )

    state = sync.update_telemetry(telem1)

    assert state.robot_id == "PV-01"
    assert state.mission_id == "MIS-TELEM"
    assert state.synchronization_status == SynchronizationStatus.SYNCHRONIZED.value
    assert state.robot_state is not None
    assert state.robot_state.battery_percent == 85.0
    assert state.robot_state.distance_m == 10.0
    assert state.robot_state.body_diameter_mm == 220.0

    # Attempt to update with older telemetry timestamp
    older_telem = RobotTelemetry(
        robot_id="PV-01",
        mission_id="MIS-TELEM",
        timestamp=now - timedelta(seconds=10),
        battery_percent=86.0,
        distance_m=9.0,
    )

    with pytest.raises(StaleUpdateError, match="older timestamp"):
        sync.update_telemetry(older_telem)


def test_stale_telemetry_detection() -> None:
    sync = DigitalTwinSynchronizer(stale_telemetry_threshold_sec=5.0)
    old_time = datetime.now(timezone.utc) - timedelta(seconds=10)

    telem = RobotTelemetry(
        robot_id="PV-01",
        mission_id="MIS-STALE",
        timestamp=old_time,
        distance_m=5.0,
    )

    state = sync.update_telemetry(telem)

    # Snapshot evaluated at current time should mark status as STALE
    assert state.synchronization_status == SynchronizationStatus.STALE.value
    assert "is stale" in state.synchronization_notes[0]


def test_mission_mismatch_rejection() -> None:
    sync = DigitalTwinSynchronizer(robot_id="PV-01", mission_id="MIS-ALPHA")

    telem_beta = RobotTelemetry(
        robot_id="PV-01",
        mission_id="MIS-BETA",
        timestamp=datetime.now(timezone.utc),
    )

    with pytest.raises(MissionMismatchError, match="does not match"):
        sync.update_telemetry(telem_beta)


def test_pose_and_observation_updates() -> None:
    sync = DigitalTwinSynchronizer(robot_id="PV-01", mission_id="MIS-OBS")
    now = datetime.now(timezone.utc)

    pose = RobotPose(
        timestamp=now,
        distance_m=12.5,
        x=12.5,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )

    sync.update_pose(pose)

    meta = InspectionFrameMetadata("MIS-OBS", 1, distance_m=12.5)
    fused = fuse_observations(RawPerceptionItem("crack", 0.85, "yolo"), meta, pose)[0]

    state = sync.add_observation(fused)

    assert state.robot_state is not None
    assert state.robot_state.pose == pose
    assert len(state.latest_observations) == 1
    assert state.latest_observations[0].class_code == "crack"


def test_recent_observations_window_limit() -> None:
    sync = DigitalTwinSynchronizer(recent_observations_limit=5)
    for i in range(1, 10):
        meta = InspectionFrameMetadata("MIS-WIN", i, distance_m=float(i))
        fused = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo"), meta)[0]
        sync.add_observation(fused)

    state = sync.snapshot()
    assert len(state.latest_observations) == 5
    assert state.latest_observations[-1].frame_index == 9


def test_end_to_end_digital_twin_aggregation_pipeline() -> None:
    sync = DigitalTwinSynchronizer(robot_id="PV-E2E", mission_id="MIS-DT-E2E")
    now = datetime.now(timezone.utc)

    # 1. Telemetry
    telem = RobotTelemetry(
        robot_id="PV-E2E",
        mission_id="MIS-DT-E2E",
        timestamp=now,
        battery_percent=92.0,
        distance_m=15.0,
        body_diameter_mm=210.0,
        state="CLEANING",
    )
    sync.update_telemetry(telem)

    # 2. Pose
    pose = RobotPose(
        timestamp=now,
        distance_m=15.0,
        x=15.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )
    sync.update_pose(pose)

    # 3. Observations & Map
    meta1 = InspectionFrameMetadata("MIS-DT-E2E", 1, distance_m=5.0)
    meta2 = InspectionFrameMetadata("MIS-DT-E2E", 2, distance_m=15.0)

    fused1 = fuse_observations(RawPerceptionItem("sediment", 0.9, "yolo"), meta1)[0]
    fused2 = fuse_observations(RawPerceptionItem("crack", 0.85, "yolo"), meta2)[0]

    sync.add_observation(fused1)
    sync.add_observation(fused2)

    inspection_map = build_inspection_map([fused1, fused2])
    sync.update_inspection_map(inspection_map)

    # 4. Morphology
    calib = MorphologyCalibration(baseline_pipe_diameter_mm=500.0, pixel_per_mm=0.5)
    morph_report = analyze_morphology(inspection_map, calibration=calib)
    sync.update_morphology(morph_report)

    # 5. Cleaning
    clean_op = CleaningOperation(
        operation_id="OP-DT-1",
        mission_id="MIS-DT-E2E",
        mode=CleaningMode.FLUSH.value,
        status=CleaningStatus.COMPLETED.value,
        start_timestamp=now,
        end_timestamp=now,
        start_distance_m=1.0,
        end_distance_m=15.0,
    )
    eff = evaluate_cleaning_effectiveness(clean_op, [fused1], [fused2])
    sync.update_cleaning(cleaning_op=clean_op, effectiveness=eff)

    # Final Snapshot
    state = sync.snapshot()

    assert state.synchronization_status == SynchronizationStatus.SYNCHRONIZED.value
    assert state.robot_state is not None
    assert state.robot_state.operational_state == "CLEANING"
    assert state.robot_state.body_diameter_mm == 210.0
    assert state.mission_state is not None
    assert state.mission_state.total_inspected_distance_m == 10.0
    assert state.inspection_map == inspection_map
    assert state.morphology_summary == morph_report
    assert state.active_cleaning_operation == clean_op
    assert state.latest_cleaning_effectiveness == eff

    # Export dictionary check
    d = state.to_dict()
    assert d["system"]["mission_id"] == "MIS-DT-E2E"
    assert d["robot"]["battery_percent"] == 92.0
    assert d["cleaning"]["active_operation"]["operation_id"] == "OP-DT-1"
