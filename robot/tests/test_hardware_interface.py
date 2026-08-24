"""Hardware Readiness & Interface Validation Tests (Phase 14)."""

from __future__ import annotations

import io
from collections.abc import Generator
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
    RobotGatewayValidationError,
)
from robot.gateway.hardware_config import create_hardware_config
from robot.gateway.models import (
    GatewayConnectionState,
    GatewayFailureReason,
    HardwareFramePacket,
)
from robot.localization.localizer import RobotLocalizer
from robot.localization.models import LocalizationQuality
from robot.telemetry.models import IMUData, RobotTelemetry
from robot.telemetry.parser import parse_telemetry
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
    img = Image.new("RGB", (64, 64), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# 1. HARDWARE CONFIGURATION VALIDATION TESTS
# ─────────────────────────────────────────────────────────────

def test_hardware_config_valid_creation() -> None:
    config = create_hardware_config(
        robot_id="ROBOT-HW-01",
        transport_type="serial",
        serial_port="/dev/ttyUSB0",
        baudrate=115200,
    )
    assert config.robot_id == "ROBOT-HW-01"
    assert config.transport_type == "serial"
    assert config.serial_port == "/dev/ttyUSB0"
    assert config.baudrate == 115200


def test_hardware_config_ethernet_validation() -> None:
    config = create_hardware_config(
        robot_id="ROBOT-HW-02",
        transport_type="ethernet",
        ethernet_host="192.168.1.100",
        ethernet_port=8080,
    )
    assert config.transport_type == "ethernet"
    assert config.ethernet_host == "192.168.1.100"
    assert config.ethernet_port == 8080


def test_hardware_config_invalid_robot_id() -> None:
    with pytest.raises(RobotGatewayValidationError, match="robot_id"):
        create_hardware_config(robot_id="")


def test_hardware_config_invalid_transport() -> None:
    with pytest.raises(RobotGatewayValidationError, match="Unsupported transport_type"):
        create_hardware_config(robot_id="ROBOT-01", transport_type="invalid_transport")


def test_hardware_config_invalid_serial_missing_port() -> None:
    with pytest.raises(RobotGatewayValidationError, match="serial_port must be specified"):
        create_hardware_config(robot_id="ROBOT-01", transport_type="serial", serial_port=None)


def test_hardware_config_invalid_ethernet_missing_host() -> None:
    with pytest.raises(RobotGatewayValidationError, match="ethernet_host must be specified"):
        create_hardware_config(robot_id="ROBOT-01", transport_type="ethernet", ethernet_host="")


# ─────────────────────────────────────────────────────────────
# 2. CAMERA CONTRACT VERIFICATION TESTS
# ─────────────────────────────────────────────────────────────

def test_camera_contract_canonical_frame_properties(db_session: Session) -> None:
    sim = SimulatorTransport(robot_id="BOT-CAM-01", mission_id="MISSION-CAM-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="BOT-CAM-01", mission_id="MISSION-CAM-01")
    gateway.connect()

    # Register robot & mission in DB
    db_session.add(Robot(robot_id="BOT-CAM-01", name="Cam Bot"))
    db_session.commit()
    MissionOrchestrator().create_mission(db_session, robot_id="BOT-CAM-01", mission_id="MISSION-CAM-01")

    img_bytes = generate_test_jpeg_bytes()
    packet = HardwareFramePacket(
        camera_id="cam-front-01",
        image_bytes=img_bytes,
        frame_index=10,
        distance_m=14.5,
    )

    res = gateway.ingest_camera_frame(packet, db=db_session)
    assert res.mission_id == "MISSION-CAM-01"
    assert res.frame_index == 10
    assert res.source == "live"
    assert res.distance_m == 14.5


def test_camera_contract_missing_optional_distance_preserved(db_session: Session) -> None:
    sim = SimulatorTransport(robot_id="BOT-CAM-02", mission_id="MISSION-CAM-02")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="BOT-CAM-02", mission_id="MISSION-CAM-02")
    gateway.connect()

    db_session.add(Robot(robot_id="BOT-CAM-02", name="Cam Bot 2"))
    db_session.commit()
    MissionOrchestrator().create_mission(db_session, robot_id="BOT-CAM-02", mission_id="MISSION-CAM-02")

    img_bytes = generate_test_jpeg_bytes()
    packet = HardwareFramePacket(
        camera_id="cam-front-02",
        image_bytes=img_bytes,
        frame_index=1,
        distance_m=None,  # Explicitly missing distance
    )

    res = gateway.ingest_camera_frame(packet, db=db_session)
    assert res.distance_m is None


# ─────────────────────────────────────────────────────────────
# 3. IMU & TELEMETRY CONTRACT VERIFICATION TESTS
# ─────────────────────────────────────────────────────────────

def test_imu_contract_fields_and_units() -> None:
    raw_imu = {"ax": 0.12, "ay": -0.05, "az": 9.81, "gx": 0.01, "gy": 0.02, "gz": -0.03}
    imu = IMUData(
        ax=raw_imu["ax"],
        ay=raw_imu["ay"],
        az=raw_imu["az"],
        gx=raw_imu["gx"],
        gy=raw_imu["gy"],
        gz=raw_imu["gz"],
    )
    assert imu.ax == 0.12
    assert imu.az == 9.81
    assert imu.gz == -0.03


def test_telemetry_contract_missing_optional_sensors_are_none() -> None:
    raw_payload = {
        "robot_id": "BOT-TELEM-01",
        "mission_id": "MISSION-TELEM-01",
        "timestamp": "2026-08-24T12:00:00Z",
    }
    telemetry = parse_telemetry(raw_payload)
    assert isinstance(telemetry, RobotTelemetry)
    assert telemetry.robot_id == "BOT-TELEM-01"
    assert telemetry.battery_percent is None
    assert telemetry.distance_m is None
    assert telemetry.imu is None
    assert telemetry.pressure is None
    assert telemetry.water is None


# ─────────────────────────────────────────────────────────────
# 4. DISTANCE & LOCALIZATION CONTRACT VERIFICATION TESTS
# ─────────────────────────────────────────────────────────────

def test_distance_contract_monotonicity_and_none_handling() -> None:
    sim = SimulatorTransport(robot_id="BOT-ODOM-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="BOT-ODOM-01")
    gateway.connect()

    payload_no_dist = {"robot_id": "BOT-ODOM-01", "timestamp": "2026-08-24T12:00:00Z"}
    telemetry_no_dist = gateway.ingest_telemetry_payload(payload_no_dist)
    assert telemetry_no_dist is not None
    assert telemetry_no_dist.distance_m is None

    payload_with_dist = {"robot_id": "BOT-ODOM-01", "timestamp": "2026-08-24T12:00:01Z", "distance_m": 8.45}
    telemetry_with_dist = gateway.ingest_telemetry_payload(payload_with_dist)
    assert telemetry_with_dist is not None
    assert telemetry_with_dist.distance_m == 8.45


def test_localization_contract_quality_enum_preservation() -> None:
    sim = SimulatorTransport(robot_id="BOT-LOC-01")
    localizer = RobotLocalizer()
    gateway = RobotGatewayAdapter(transport=sim, robot_id="BOT-LOC-01", localizer=localizer)
    gateway.connect()

    assert gateway.get_current_pose() is None  # Initial state is None

    # Telemetry without IMU -> Localization quality is DEGRADED
    payload_no_imu = {
        "robot_id": "BOT-LOC-01",
        "timestamp": "2026-08-24T12:00:00Z",
        "distance_m": 10.0,
    }
    gateway.ingest_telemetry_payload(payload_no_imu)
    pose = gateway.get_current_pose()
    assert pose is not None
    assert pose.quality == LocalizationQuality.DEGRADED
    assert pose.distance_m == 10.0

    # Telemetry with IMU -> Localization quality is TRACKING
    payload_with_imu = {
        "robot_id": "BOT-LOC-01",
        "timestamp": "2026-08-24T12:00:01Z",
        "distance_m": 10.2,
        "imu": {"ax": 0.0, "ay": 0.0, "az": 9.81, "gx": 0.0, "gy": 0.0, "gz": 0.01},
    }
    gateway.ingest_telemetry_payload(payload_with_imu)
    pose_tracking = gateway.get_current_pose()
    assert pose_tracking is not None
    assert pose_tracking.quality == LocalizationQuality.TRACKING
    assert pose_tracking.distance_m == 10.2


# ─────────────────────────────────────────────────────────────
# 5. COMMAND & SAFETY CONTRACT VERIFICATION TESTS
# ─────────────────────────────────────────────────────────────

def test_command_contract_all_supported_protocol_methods() -> None:
    sim = SimulatorTransport(robot_id="BOT-CMD-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="BOT-CMD-01")
    gateway.connect()

    gateway.move(linear=0.5, angular=0.0)
    assert gateway.controller.state == ControllerState.MOVING

    gateway.camera_pan(angle_deg=45.0)
    gateway.clean_start(mode="JETTING")
    gateway.clean_stop()
    gateway.inflate(target_pressure_kpa=150.0)
    gateway.hold_pressure(target_pressure_kpa=150.0)
    gateway.deflate()
    gateway.sample_open()
    gateway.sample_close()

    gateway.stop()
    assert gateway.controller.state == ControllerState.IDLE


def test_emergency_stop_independence_from_external_services() -> None:
    sim = SimulatorTransport(robot_id="BOT-ESTOP-01")
    # Gateway without DB, without orchestrator, without localizer
    gateway = RobotGatewayAdapter(transport=sim, robot_id="BOT-ESTOP-01")
    gateway.connect()

    gateway.move(linear=0.3, angular=0.1)
    assert gateway.controller.state == ControllerState.MOVING

    # Trigger emergency stop directly
    gateway.emergency_stop()
    assert gateway.controller.state == ControllerState.EMERGENCY_STOP

    # Post-emergency stop movement must raise ControllerSafetyError
    with pytest.raises(ControllerSafetyError):
        gateway.move(linear=0.1, angular=0.0)


# ─────────────────────────────────────────────────────────────
# 6. LIFECYCLE & TIMEOUT VERIFICATION TESTS
# ─────────────────────────────────────────────────────────────

def test_lifecycle_connect_disconnect_reconnect_flow() -> None:
    sim = SimulatorTransport(robot_id="BOT-LIFE-01")
    gateway = RobotGatewayAdapter(transport=sim, robot_id="BOT-LIFE-01")

    assert gateway.connection_state == GatewayConnectionState.DISCONNECTED

    gateway.connect()
    assert gateway.connection_state == GatewayConnectionState.CONNECTED

    gateway.disconnect()
    assert gateway.connection_state == GatewayConnectionState.DISCONNECTED

    gateway.connect()
    assert gateway.connection_state == GatewayConnectionState.CONNECTED


def test_telemetry_timeout_detection() -> None:
    sim = SimulatorTransport(robot_id="BOT-TIMEOUT-01")
    gateway = RobotGatewayAdapter(
        transport=sim,
        robot_id="BOT-TIMEOUT-01",
        telemetry_timeout_s=0.1,
    )
    gateway.connect()
    gateway.ingest_telemetry_payload({"robot_id": "BOT-TIMEOUT-01"})
    assert gateway.connection_state == GatewayConnectionState.STREAMING

    import time
    time.sleep(0.15)

    health = gateway.get_health()
    assert health.failure_reason == GatewayFailureReason.TELEMETRY_TIMEOUT
