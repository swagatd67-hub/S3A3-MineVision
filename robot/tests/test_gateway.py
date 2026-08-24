"""Focused tests for Robot Gateway / Hardware Adapter (Phase 13)."""

from __future__ import annotations

import io
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db import Base
from backend.app.models import Robot
from backend.app.services.mission.orchestrator import MissionOrchestrator
from backend.app.services.video.sewer_classifier import ClassDecision, SewerMLResult
from robot.control.robot_controller import ControllerSafetyError, ControllerState
from robot.gateway.adapter import RobotGatewayAdapter
from robot.gateway.exceptions import (
    RobotGatewayConnectionError,
    RobotGatewayValidationError,
)
from robot.gateway.models import (
    GatewayConnectionState,
    GatewayFailureReason,
    HardwareFramePacket,
)
from robot.localization.localizer import RobotLocalizer
from robot.localization.models import LocalizationQuality, RobotPose
from robot.transport.base import RobotTransport, TransportConnectionError
from robot.transport.simulator import SimulatorTransport


class StubSewerMLEngine:
    """Deterministic test double for Sewer-ML classification engine."""

    def __init__(self, detected_classes: list[str] | None = None) -> None:
        self.detected_classes = detected_classes if detected_classes is not None else ["CR"]
        self.model_version = "sewer-ml-stub"

    def predict(self, image: Any) -> SewerMLResult:
        decisions = [
            ClassDecision(
                class_code="CR",
                probability=0.95,
                threshold=0.5,
                detected=True,
            )
        ]
        return SewerMLResult(
            decisions=decisions,
            detected_classes=["CR"],
            inference_ms=1.0,
            model_version=self.model_version,
        )


@pytest.fixture(autouse=True)
def stub_ai_engines(monkeypatch: pytest.MonkeyPatch) -> StubSewerMLEngine:
    """Inject deterministic test double for Sewer-ML engine during gateway tests."""
    stub_engine = StubSewerMLEngine()
    monkeypatch.setattr(
        "backend.app.services.inspection.gateway.get_sewer_classifier_engine",
        lambda *args, **kwargs: stub_engine,
    )
    return stub_engine


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """In-memory SQLite DB session fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def generate_test_jpeg_bytes() -> bytes:
    """Generate a minimal valid 64x64 JPEG image in bytes."""
    img = Image.new("RGB", (64, 64), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class FailingTransport(RobotTransport):
    """Transport that fails on connect and send."""

    def connect(self) -> None:
        raise TransportConnectionError("Hardware link down")

    def disconnect(self) -> None:
        pass

    @property
    def is_connected(self) -> bool:
        return False

    def send(self, message: dict[str, Any] | str) -> None:
        raise TransportConnectionError("Send failed")

    def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None:
        return None


# ─────────────────────────────────────────────────────────────
# 1. TRANSPORT TESTS
# ─────────────────────────────────────────────────────────────

def test_gateway_simulator_transport_connection() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01", mission_id="MISSION-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01", mission_id="MISSION-01")

    assert gateway.connection_state == GatewayConnectionState.DISCONNECTED
    assert not gateway.is_connected

    gateway.connect()
    assert gateway.connection_state == GatewayConnectionState.CONNECTED
    assert gateway.is_connected
    assert sim.is_connected

    gateway.disconnect()
    assert gateway.connection_state == GatewayConnectionState.DISCONNECTED
    assert not gateway.is_connected
    assert not sim.is_connected


def test_gateway_connection_failure() -> None:
    fail_tr = FailingTransport()
    gateway = RobotGatewayAdapter(transport=fail_tr)

    with pytest.raises(RobotGatewayConnectionError, match="Failed to connect"):
        gateway.connect()

    assert gateway.connection_state == GatewayConnectionState.DISCONNECTED
    assert gateway.failure_reason == GatewayFailureReason.CONNECTION_FAILED
    assert gateway.get_health().error_count == 1


def test_gateway_reconnect() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01")

    gateway.connect()
    assert gateway.is_connected
    gateway.disconnect()
    assert not gateway.is_connected

    gateway.connect()
    assert gateway.is_connected


# ─────────────────────────────────────────────────────────────
# 2. TELEMETRY TESTS
# ─────────────────────────────────────────────────────────────

def test_gateway_valid_telemetry_normalization() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01", mission_id="MISSION-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01", mission_id="MISSION-01")
    gateway.connect()

    raw_payload = {
        "robot_id": "ROBOT-01",
        "mission_id": "MISSION-01",
        "timestamp": "2026-08-24T10:00:00Z",
        "battery_percent": 88.5,
        "distance_m": 12.4,
        "body_diameter_mm": 110.0,
        "state": "INSPECTING",
        "imu": {"ax": 0.1, "ay": 0.0, "az": 9.81, "gx": 0.0, "gy": 0.0, "gz": 0.05},
    }

    telemetry = gateway.ingest_telemetry_payload(raw_payload)
    assert telemetry is not None
    assert telemetry.robot_id == "ROBOT-01"
    assert telemetry.mission_id == "MISSION-01"
    assert telemetry.battery_percent == 88.5
    assert telemetry.distance_m == 12.4
    assert telemetry.imu is not None
    assert telemetry.imu.gz == 0.05
    assert gateway.connection_state == GatewayConnectionState.STREAMING
    assert gateway.failure_reason == GatewayFailureReason.NONE


def test_gateway_malformed_telemetry_rejected() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01")
    gateway.connect()

    malformed = {"mission_id": "MISSION-01"}  # Missing required robot_id

    with pytest.raises(RobotGatewayValidationError, match="robot_id"):
        gateway.ingest_telemetry_payload(malformed)

    assert gateway.failure_reason == GatewayFailureReason.INVALID_DATA


def test_gateway_missing_optional_fields_not_fabricated() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01")
    gateway.connect()

    minimal_payload = {"robot_id": "ROBOT-01"}
    telemetry = gateway.ingest_telemetry_payload(minimal_payload)

    assert telemetry is not None
    assert telemetry.battery_percent is None
    assert telemetry.distance_m is None
    assert telemetry.body_diameter_mm is None
    assert telemetry.imu is None
    assert telemetry.pressure is None
    assert telemetry.water is None


def test_gateway_mission_mismatch_rejected() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01", mission_id="EXPECTED-MISSION")
    gateway = RobotGatewayAdapter(
        transport=sim, robot_id="ROBOT-01", mission_id="EXPECTED-MISSION"
    )
    gateway.connect()

    mismatched = {
        "robot_id": "ROBOT-01",
        "mission_id": "OTHER-MISSION",
    }

    with pytest.raises(RobotGatewayValidationError, match="mission_id"):
        gateway.ingest_telemetry_payload(mismatched)

    assert gateway.failure_reason == GatewayFailureReason.MISSION_MISMATCH


# ─────────────────────────────────────────────────────────────
# 3. LOCALIZATION TESTS
# ─────────────────────────────────────────────────────────────

def test_gateway_localization_integration_via_localizer() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01", mission_id="MISSION-01")
    localizer = RobotLocalizer()
    gateway = RobotGatewayAdapter(
        transport=sim,
        robot_id="ROBOT-01",
        mission_id="MISSION-01",
        localizer=localizer,
    )
    gateway.connect()

    payload = {
        "robot_id": "ROBOT-01",
        "mission_id": "MISSION-01",
        "timestamp": "2026-08-24T10:00:00Z",
        "distance_m": 5.0,
        "imu": {"ax": 0.0, "ay": 0.0, "az": 9.81, "gx": 0.0, "gy": 0.0, "gz": 0.02},
    }

    gateway.ingest_telemetry_payload(payload)
    pose = gateway.get_current_pose()

    assert pose is not None
    assert pose.distance_m == 5.0
    assert pose.x == 5.0
    assert pose.y == 0.0
    assert pose.quality == LocalizationQuality.TRACKING


def test_gateway_direct_pose_ingestion() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01")
    gateway.connect()

    pose = RobotPose(
        timestamp=datetime.now(timezone.utc),
        distance_m=15.2,
        x=15.2,
        y=0.0,
        heading_rad=0.1,
        heading_deg=5.73,
        quality=LocalizationQuality.TRACKING,
        source="external_lidar",
    )

    ingested = gateway.ingest_pose(pose)
    assert ingested.distance_m == 15.2
    assert gateway.get_current_pose() == pose


def test_gateway_unavailable_localization_not_fabricated() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01")
    gateway.connect()

    assert gateway.get_current_pose() is None


# ─────────────────────────────────────────────────────────────
# 4. VISION / CAMERA FRAME ADAPTER TESTS
# ─────────────────────────────────────────────────────────────

def test_gateway_camera_frame_ingestion(db_session: Session) -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01", mission_id="M-100")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01", mission_id="M-100")
    gateway.connect()

    # Register robot & mission in DB
    robot_row = Robot(robot_id="ROBOT-01", name="Bot 1")
    db_session.add(robot_row)
    db_session.commit()
    MissionOrchestrator().create_mission(db_session, robot_id="ROBOT-01", mission_id="M-100")

    img_bytes = generate_test_jpeg_bytes()
    packet = HardwareFramePacket(
        camera_id="cam-front-01",
        image_bytes=img_bytes,
        frame_index=1,
        distance_m=2.5,
    )

    res = gateway.ingest_camera_frame(packet, db=db_session)
    assert res.mission_id == "M-100"
    assert res.frame_index == 1
    assert res.distance_m == 2.5
    assert res.source == "live"
    assert gateway.get_health().frame_count == 1


# ─────────────────────────────────────────────────────────────
# 5. MISSION INTEGRATION & COMMAND ROUTING TESTS
# ─────────────────────────────────────────────────────────────

def test_gateway_mission_data_flow(db_session: Session) -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01", mission_id="M-200")
    localizer = RobotLocalizer()
    gateway = RobotGatewayAdapter(
        transport=sim,
        robot_id="ROBOT-01",
        mission_id="M-200",
        localizer=localizer,
    )
    gateway.connect()

    # Register robot & mission
    db_session.add(Robot(robot_id="ROBOT-01", name="Bot"))
    db_session.commit()
    MissionOrchestrator().create_mission(db_session, robot_id="ROBOT-01", mission_id="M-200")

    # Ingest telemetry
    telem_payload = {
        "robot_id": "ROBOT-01",
        "mission_id": "M-200",
        "timestamp": "2026-08-24T10:00:00Z",
        "distance_m": 4.0,
        "imu": {"ax": 0.0, "ay": 0.0, "az": 9.81, "gx": 0.0, "gy": 0.0, "gz": 0.0},
    }
    gateway.ingest_telemetry_payload(telem_payload, db=db_session)

    # Ingest camera frame
    img_bytes = generate_test_jpeg_bytes()
    gateway.ingest_camera_frame(
        HardwareFramePacket(
            camera_id="cam-0",
            image_bytes=img_bytes,
            frame_index=1,
        ),
        db=db_session,
    )

    snapshot = MissionOrchestrator().get_mission_snapshot(db_session, "M-200")
    assert snapshot.mission_id == "M-200"
    assert snapshot.progress.current_distance_m == 4.0


def test_gateway_command_routing() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="ROBOT-01")
    gateway.connect()

    gateway.move(0.4, 0.1)
    assert gateway.controller.state == ControllerState.MOVING

    gateway.stop()
    assert gateway.controller.state == ControllerState.IDLE

    gateway.camera_pan(30.0)
    gateway.clean_start("JETTING")
    gateway.clean_stop()

    gateway.emergency_stop()
    assert gateway.controller.state == ControllerState.EMERGENCY_STOP

    # Movement after emergency stop must fail
    with pytest.raises(ControllerSafetyError):
        gateway.move(0.2, 0.0)


def test_gateway_poll_with_simulator() -> None:
    sim = SimulatorTransport(robot_id="PV-SIM-001", mission_id="SIM-MISSION-001")
    localizer = RobotLocalizer()
    gateway = RobotGatewayAdapter(
        transport=sim,
        robot_id="PV-SIM-001",
        mission_id="SIM-MISSION-001",
        localizer=localizer,
    )
    gateway.connect()

    telemetry = gateway.poll()
    assert telemetry is not None
    assert telemetry.robot_id == "PV-SIM-001"
    assert telemetry.mission_id == "SIM-MISSION-001"
    assert gateway.latest_telemetry == telemetry
    assert gateway.latest_pose is not None


def test_gateway_health_and_timeouts() -> None:
    sim = SimulatorTransport(robot_id="ROBOT-01")
    gateway = RobotGatewayAdapter(
        transport=sim,
        robot_id="ROBOT-01",
        telemetry_timeout_s=0.1,
    )
    gateway.connect()

    health_initial = gateway.get_health()
    assert health_initial.is_connected
    assert health_initial.is_healthy
    assert health_initial.failure_reason == GatewayFailureReason.NONE
