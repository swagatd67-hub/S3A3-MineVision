"""Comprehensive Unit & Integration Tests for Backend Mission Orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db import SessionLocal, init_db
from backend.app.main import app
from backend.app.models import Robot
from backend.app.services.inspection.fusion import fuse_observations
from backend.app.services.inspection.models import (
    BoundingBox,
    InspectionFrameMetadata,
    RawPerceptionItem,
)
from backend.app.services.mission.exceptions import (
    InvalidMissionLifecycleError,
    MissionNotFoundError,
    RobotMismatchError,
)
from backend.app.services.mission.models import MissionLifecycleState
from backend.app.services.mission.orchestrator import MissionOrchestrator
from cleaning.models import CleaningMode, CleaningOperation, CleaningStatus
from morphology.models import MorphologyCalibration
from robot.localization.models import LocalizationQuality, RobotPose


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def _ensure_robot(db, robot_id: str, name: str) -> Robot:
    robot = db.get(Robot, robot_id)
    if robot is None:
        robot = Robot(robot_id=robot_id, name=name)
        db.add(robot)
        db.commit()
        db.refresh(robot)
    return robot


def test_mission_lifecycle_flow() -> None:
    db = SessionLocal()
    orchestrator = MissionOrchestrator()

    robot_id = f"PV-ORCH-{uuid4().hex[:6]}"
    _ensure_robot(db, robot_id, "Crawler Alpha")

    # 1. Create Mission
    mission = orchestrator.create_mission(db, robot_id=robot_id, objective="INSPECT")
    mission_id = mission.mission_id

    assert mission.status == MissionLifecycleState.CREATED.value
    assert mission.robot_id == robot_id

    # 2. Start Mission
    started = orchestrator.start_mission(db, mission_id)
    assert started.status == MissionLifecycleState.RUNNING.value
    assert started.started_at is not None

    # Duplicate start should be idempotent
    started_dup = orchestrator.start_mission(db, mission_id)
    assert started_dup.status == MissionLifecycleState.RUNNING.value

    # 3. Pause Mission
    paused = orchestrator.pause_mission(db, mission_id)
    assert paused.status == MissionLifecycleState.PAUSED.value

    # 4. Resume Mission
    resumed = orchestrator.resume_mission(db, mission_id)
    assert resumed.status == MissionLifecycleState.RUNNING.value

    # 5. Complete Mission
    completed = orchestrator.complete_mission(db, mission_id)
    assert completed.status == MissionLifecycleState.COMPLETED.value
    assert completed.completed_at is not None

    # Invalid transition from COMPLETED to RUNNING
    with pytest.raises(InvalidMissionLifecycleError):
        orchestrator.start_mission(db, mission_id)

    db.close()


def test_unregistered_robot_rejection() -> None:
    db = SessionLocal()
    orchestrator = MissionOrchestrator()

    with pytest.raises(RobotMismatchError, match="not registered"):
        orchestrator.create_mission(db, robot_id=f"PV-NONEXISTENT-{uuid4().hex[:6]}")

    db.close()


def test_missing_mission_operations() -> None:
    db = SessionLocal()
    orchestrator = MissionOrchestrator()

    missing_id = f"M-MISSING-{uuid4().hex[:6]}"

    with pytest.raises(MissionNotFoundError):
        orchestrator.start_mission(db, missing_id)

    with pytest.raises(MissionNotFoundError):
        orchestrator.get_mission_snapshot(db, missing_id)

    db.close()


def test_telemetry_and_localization_ingestion() -> None:
    db = SessionLocal()
    orchestrator = MissionOrchestrator()

    robot_id = f"PV-TELEM-{uuid4().hex[:6]}"
    _ensure_robot(db, robot_id, "Crawler Telemetry")

    mission = orchestrator.create_mission(db, robot_id=robot_id)
    mission_id = mission.mission_id
    orchestrator.start_mission(db, mission_id)

    now = datetime.now(timezone.utc)
    packet = {
        "robot_id": robot_id,
        "timestamp": now.isoformat(),
        "battery_percent": 88.5,
        "distance_m": 14.2,
        "body_diameter_mm": 220.0,
        "state": "MOVING",
    }

    twin_state = orchestrator.ingest_telemetry(db, mission_id, packet)
    assert twin_state.robot_id == robot_id
    assert twin_state.robot_state is not None
    assert twin_state.robot_state.battery_percent == 88.5
    assert twin_state.robot_state.distance_m == 14.2

    pose = RobotPose(
        timestamp=now,
        distance_m=14.2,
        x=14.2,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )
    twin_pose_state = orchestrator.ingest_pose(db, mission_id, pose)
    assert twin_pose_state.robot_state is not None
    assert twin_pose_state.robot_state.pose == pose

    db.close()


def test_fused_observation_ingestion_and_idempotency() -> None:
    db = SessionLocal()
    orchestrator = MissionOrchestrator()

    robot_id = f"PV-OBS-{uuid4().hex[:6]}"
    _ensure_robot(db, robot_id, "Crawler Observation")

    mission = orchestrator.create_mission(db, robot_id=robot_id)
    mission_id = mission.mission_id
    orchestrator.start_mission(db, mission_id)

    meta = InspectionFrameMetadata(mission_id, 10, distance_m=5.5)
    item = RawPerceptionItem("crack", 0.92, "yolo_v8", box=BoundingBox(10.0, 20.0, 50.0, 60.0))
    fused = fuse_observations(item, meta)[0]

    twin_state = orchestrator.ingest_inspection_observation(db, mission_id, fused)
    assert len(twin_state.latest_observations) == 1
    assert twin_state.latest_observations[0].observation_id == fused.observation_id

    # Ingest duplicate observation ID idempotently
    twin_state_dup = orchestrator.ingest_inspection_observation(db, mission_id, fused)
    assert len(twin_state_dup.latest_observations) == 1

    db.close()


def test_end_to_end_mission_orchestration_pipeline() -> None:
    db = SessionLocal()
    orchestrator = MissionOrchestrator()

    robot_id = f"PV-E2E-{uuid4().hex[:6]}"
    _ensure_robot(db, robot_id, "Crawler E2E Orchestration")

    # Create & Start Mission
    mission = orchestrator.create_mission(db, robot_id=robot_id, objective="INSPECT_AND_CLEAN")
    mission_id = mission.mission_id
    orchestrator.start_mission(db, mission_id)

    now = datetime.now(timezone.utc)

    # Ingest Telemetry
    orchestrator.ingest_telemetry(
        db,
        mission_id,
        {
            "robot_id": robot_id,
            "timestamp": now.isoformat(),
            "battery_percent": 95.0,
            "distance_m": 20.0,
            "body_diameter_mm": 200.0,
            "state": "INSPECTING",
        },
    )

    # Ingest Pose
    pose = RobotPose(
        timestamp=now,
        distance_m=20.0,
        x=20.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )
    orchestrator.ingest_pose(db, mission_id, pose)

    # Ingest Observations
    meta1 = InspectionFrameMetadata(mission_id, 1, distance_m=5.0)
    meta2 = InspectionFrameMetadata(mission_id, 2, distance_m=20.0)

    obs1 = fuse_observations(RawPerceptionItem("deposit", 0.88, "sewer_ml"), meta1, pose)[0]
    obs2 = fuse_observations(RawPerceptionItem("crack", 0.95, "yolo_v8"), meta2, pose)[0]

    orchestrator.ingest_inspection_observation(db, mission_id, obs1)
    orchestrator.ingest_inspection_observation(db, mission_id, obs2)

    # Update Mapping
    inspection_map = orchestrator.update_mapping(db, mission_id)
    assert inspection_map.observation_count == 2

    # Update Morphology
    morph_report = orchestrator.update_morphology(
        db, mission_id, calibration=MorphologyCalibration(baseline_pipe_diameter_mm=500.0)
    )
    assert morph_report.total_observations == 2

    # Update Cleaning
    clean_op = CleaningOperation(
        operation_id=f"OP-E2E-{uuid4().hex[:6]}",
        mission_id=mission_id,
        mode=CleaningMode.FLUSH.value,
        status=CleaningStatus.COMPLETED.value,
        start_timestamp=now,
        end_timestamp=now,
        start_distance_m=0.0,
        end_distance_m=20.0,
    )
    orchestrator.update_cleaning(db, mission_id, clean_op)

    # Mission Snapshot
    snapshot = orchestrator.get_mission_snapshot(db, mission_id)
    d = snapshot.to_dict()

    assert d["mission_id"] == mission_id
    assert d["robot_id"] == robot_id
    assert d["status"] == MissionLifecycleState.RUNNING.value
    assert d["progress"]["current_distance_m"] == 20.0
    assert d["progress"]["observation_count"] == 2
    assert d["digital_twin"]["system"]["synchronization_status"] == "SYNCHRONIZED"

    # Complete Mission
    orchestrator.complete_mission(db, mission_id)
    completed_snapshot = orchestrator.get_mission_snapshot(db, mission_id)
    assert completed_snapshot.status == MissionLifecycleState.COMPLETED.value

    db.close()


def test_api_mission_endpoints() -> None:
    client = TestClient(app)

    robot_id = f"PV-API-{uuid4().hex[:6]}"

    # Register robot
    r_reg = client.post(
        "/api/v1/robots/register",
        json={
            "robot_id": robot_id,
            "name": "API Tester Robot",
            "capabilities": ["camera", "imu"],
        },
    )
    assert r_reg.status_code == 200

    # Create Mission
    r_create = client.post(
        "/api/v1/missions",
        json={"robot_id": robot_id, "objective": "INSPECT_AND_CLEAN"},
    )
    assert r_create.status_code == 201
    mission_data = r_create.json()
    mission_id = mission_data["mission_id"]
    assert mission_data["status"] == "CREATED"

    # Start Mission
    r_start = client.post(f"/api/v1/missions/{mission_id}/start")
    assert r_start.status_code == 200
    assert r_start.json()["status"] == "RUNNING"

    # Pause Mission
    r_pause = client.post(f"/api/v1/missions/{mission_id}/pause")
    assert r_pause.status_code == 200
    assert r_pause.json()["status"] == "PAUSED"

    # Resume Mission
    r_resume = client.post(f"/api/v1/missions/{mission_id}/resume")
    assert r_resume.status_code == 200
    assert r_resume.json()["status"] == "RUNNING"

    # Snapshot API
    r_snap = client.get(f"/api/v1/missions/{mission_id}/snapshot")
    assert r_snap.status_code == 200
    snap_body = r_snap.json()
    assert snap_body["mission_id"] == mission_id
    assert "digital_twin" in snap_body

    # Digital Twin API
    r_dt = client.get(f"/api/v1/missions/{mission_id}/digital_twin")
    assert r_dt.status_code == 200
    assert r_dt.json()["system"]["mission_id"] == mission_id

    # Complete Mission
    r_comp = client.post(f"/api/v1/missions/{mission_id}/complete")
    assert r_comp.status_code == 200
    assert r_comp.json()["status"] == "COMPLETED"
