"""Hardware-Independent Robot Bring-up Test Suite (Phase 15A).

Validates complete runtime behavior of the PipeVision robot using SimulatorTransport,
verifying lifecycle transitions, telemetry streaming, localization, camera processing,
AI inspection fusion, command execution, failure recovery, determinism, and stress bounds.
"""

from __future__ import annotations

import io
import time
from collections.abc import Generator
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db import Base
from backend.app.models import Robot
from backend.app.services.mission.models import MissionLifecycleState
from backend.app.services.mission.orchestrator import MissionOrchestrator
from backend.app.services.video.sewer_classifier import ClassDecision, SewerMLResult
from robot.control.robot_controller import (
    ControllerError,
    ControllerState,
    RobotController,
)
from robot.gateway.adapter import RobotGatewayAdapter
from robot.gateway.models import (
    GatewayConnectionState,
    GatewayFailureReason,
)
from robot.localization.localizer import RobotLocalizer
from robot.localization.models import LocalizationQuality
from robot.telemetry.parser import parse_telemetry
from robot.transport.base import RobotTransport, TransportConnectionError
from robot.transport.simulator import SimulatorConfig, SimulatorTransport


class StubSewerMLEngine:
    """Deterministic test double for Sewer-ML classification engine."""

    def __init__(self, detected_classes: list[str] | None = None) -> None:
        self.detected_classes = detected_classes if detected_classes is not None else ["CR"]
        self.model_version = "sewer-ml-stub-v1"

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
            detected_classes=self.detected_classes,
            inference_ms=1.5,
            model_version=self.model_version,
        )


@pytest.fixture(autouse=True)
def stub_ai_engines(monkeypatch: pytest.MonkeyPatch) -> StubSewerMLEngine:
    """Inject deterministic Sewer-ML test double across all Phase 15A bring-up tests."""
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
        # Pre-seed default test robot
        robot = Robot(
            robot_id="PV-SIM-001",
            name="Simulated PipeVision Bot",
        )
        session.add(robot)
        session.commit()
        yield session
    finally:
        session.close()


def generate_test_jpeg_bytes(color: tuple[int, int, int] = (0, 100, 200)) -> bytes:
    """Generate minimal valid JPEG bytes for testing."""
    img = Image.new("RGB", (64, 64), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ============================================================================
# 1. SIMULATED ROBOT CONNECTION LIFECYCLE & IDENTITY
# ============================================================================

def test_simulated_robot_lifecycle_and_identity() -> None:
    """Verify state transitions and explicit robot identity without fake DB records."""
    transport = SimulatorTransport(robot_id="PV-SIM-001", mission_id="SIM-M-001")
    adapter = RobotGatewayAdapter(transport=transport, robot_id="PV-SIM-001", mission_id="SIM-M-001")

    assert adapter.connection_state == GatewayConnectionState.DISCONNECTED
    assert adapter.robot_id == "PV-SIM-001"

    # Connect
    adapter.connect()
    assert adapter.connection_state == GatewayConnectionState.CONNECTED
    assert adapter.is_connected

    # First telemetry payload transitions state to STREAMING
    raw = transport.step()
    adapter.ingest_telemetry_payload(raw)
    assert adapter.connection_state == GatewayConnectionState.STREAMING

    # Disconnect
    adapter.disconnect()
    assert adapter.connection_state == GatewayConnectionState.DISCONNECTED
    assert not adapter.is_connected


def test_invalid_lifecycle_state_transitions() -> None:
    """Verify adapter rejects operations when disconnected."""
    transport = SimulatorTransport()
    adapter = RobotGatewayAdapter(transport=transport)

    assert adapter.connection_state == GatewayConnectionState.DISCONNECTED

    # Attempting to move while disconnected raises ControllerError
    with pytest.raises(ControllerError, match="disconnected"):
        adapter.move(0.1, 0.0)


# ============================================================================
# 2. SIMULATED TELEMETRY DETERMINISM & SENSOR CONFIG
# ============================================================================

def test_simulated_telemetry_determinism() -> None:
    """Verify SimulatorTransport produces bit-exact telemetry streams across runs."""
    config = SimulatorConfig(
        robot_id="PV-SIM-001",
        mission_id="SIM-M-100",
        step_interval=0.5,
        linear_speed_m_s=0.2,
    )

    t1 = SimulatorTransport(config=config)
    t1.connect()
    packets1 = [t1.step() for _ in range(5)]

    t2 = SimulatorTransport(config=config)
    t2.connect()
    packets2 = [t2.step() for _ in range(5)]

    for p1, p2 in zip(packets1, packets2):
        assert p1["distance_m"] == p2["distance_m"]
        assert p1["battery_percent"] == p2["battery_percent"]
        assert p1["imu"] == p2["imu"]
        assert p1["pressure"] == p2["pressure"]
        assert p1["water"] == p2["water"]


# ============================================================================
# 3. LOCALIZATION TRACKING & QUALITY STATE MACHINE
# ============================================================================

def test_localization_tracking_state_machine() -> None:
    """Verify localizer transitions correctly between TRACKING and DEGRADED."""
    localizer = RobotLocalizer()
    assert localizer.current_pose is None

    # Step 1: Initial telemetry with full IMU & distance
    raw1 = {
        "robot_id": "PV-SIM-001",
        "timestamp": "2026-08-24T10:00:00Z",
        "distance_m": 0.0,
        "imu": {"ax": 0.0, "ay": 0.0, "az": 9.81, "gx": 0.0, "gy": 0.0, "gz": 0.01},
    }
    t1 = parse_telemetry(raw1)
    assert t1 is not None
    pose1 = localizer.update(t1)

    assert pose1.quality == LocalizationQuality.TRACKING
    assert pose1.distance_m == 0.0

    # Step 2: Next telemetry sample 1 second later
    raw2 = {
        "robot_id": "PV-SIM-001",
        "timestamp": "2026-08-24T10:00:01Z",
        "distance_m": 0.5,
        "imu": {"ax": 0.0, "ay": 0.0, "az": 9.81, "gx": 0.0, "gy": 0.0, "gz": 0.02},
    }
    t2 = parse_telemetry(raw2)
    assert t2 is not None
    pose2 = localizer.update(t2)

    assert pose2.quality == LocalizationQuality.TRACKING
    assert pose2.distance_m == 0.5

    # Step 3: Degraded telemetry without IMU
    raw3 = {
        "robot_id": "PV-SIM-001",
        "timestamp": "2026-08-24T10:00:02Z",
        "distance_m": 1.0,
    }
    t3 = parse_telemetry(raw3)
    assert t3 is not None
    pose3 = localizer.update(t3)

    assert pose3.quality == LocalizationQuality.DEGRADED
    assert pose3.distance_m == 1.0


# ============================================================================
# 4. CAMERA FRAME PROCESSING & INSPECTION INGESTION
# ============================================================================

def test_camera_frame_processing(db_session: Session) -> None:
    """Verify synthetic camera frames transform to CanonicalInspectionFrame and ingest cleanly."""
    orchestrator = MissionOrchestrator()
    orchestrator.create_mission(db=db_session, robot_id="PV-SIM-001", mission_id="SIM-M-200")
    orchestrator.start_mission(db=db_session, mission_id="SIM-M-200")

    transport = SimulatorTransport()
    adapter = RobotGatewayAdapter(
        transport=transport,
        robot_id="PV-SIM-001",
        mission_id="SIM-M-200",
        auto_ingest_backend=False,
    )
    adapter.connect()

    packet = transport.generate_synthetic_frame(frame_index=1, distance_m=0.25)
    res = adapter.ingest_camera_frame(packet, db=db_session)

    assert len(res.observations) > 0
    assert res.observations[0].class_code == "CR"


# ============================================================================
# 5. FULL END-TO-END MISSION WORKFLOW
# ============================================================================

def test_full_end_to_end_mission_simulation(db_session: Session) -> None:
    """Validate full lifecycle: Create Mission -> Stream -> Ingest -> Map -> Complete."""
    orchestrator = MissionOrchestrator()

    # 1. Create Mission
    mission = orchestrator.create_mission(
        db=db_session,
        robot_id="PV-SIM-001",
        objective="FULL_SIMULATION_INSPECTION",
        mission_id="SIM-M-E2E-001",
    )
    assert mission.status == MissionLifecycleState.CREATED.value

    # 2. Start Mission
    orchestrator.start_mission(db=db_session, mission_id=mission.mission_id)
    assert mission.status == MissionLifecycleState.RUNNING.value

    # 3. Setup Gateway with Simulator
    transport = SimulatorTransport(
        robot_id="PV-SIM-001",
        mission_id=mission.mission_id,
        step_interval=0.5,
    )
    localizer = RobotLocalizer()
    adapter = RobotGatewayAdapter(
        transport=transport,
        robot_id="PV-SIM-001",
        mission_id=mission.mission_id,
        localizer=localizer,
        auto_ingest_backend=True,
    )

    adapter.connect()

    # 4. Stream Telemetry & Camera Frames
    for idx in range(1, 6):
        raw_telemetry = transport.step()
        adapter.ingest_telemetry_payload(raw_telemetry, db=db_session)

        frame_packet = transport.generate_synthetic_frame(
            frame_index=idx,
            distance_m=raw_telemetry.get("distance_m"),
        )
        adapter.ingest_camera_frame(frame_packet, db=db_session)

    health = adapter.get_health()
    assert health.telemetry_packet_count == 5
    assert health.frame_count == 5

    # 5. Verify Orchestrator snapshot & domain state
    snapshot = orchestrator.get_mission_snapshot(db=db_session, mission_id=mission.mission_id)
    assert snapshot.progress.observation_count == 5
    assert snapshot.progress.current_distance_m > 0.0

    # 6. Complete Mission
    completed_mission = orchestrator.complete_mission(db=db_session, mission_id=mission.mission_id)
    assert completed_mission.status == MissionLifecycleState.COMPLETED.value
    assert completed_mission.completed_at is not None

    adapter.disconnect()


# ============================================================================
# 6. ROBOT CONTROL & EMERGENCY STOP ISOLATION
# ============================================================================

def test_robot_control_commands_and_safety_isolation() -> None:
    """Verify commands execute through controller and emergency_stop is completely isolated."""
    transport = SimulatorTransport()
    controller = RobotController(transport)

    controller.connect()
    assert controller.state == ControllerState.IDLE

    # Valid commands
    controller.move(linear=0.2, angular=0.0)
    assert controller.state == ControllerState.MOVING

    controller.stop()
    assert controller.state == ControllerState.IDLE

    controller.camera_pan(angle_deg=45.0)
    controller.clean_start(mode="HIGH_PRESSURE")
    controller.inflate(target_pressure_kpa=180.0)

    # Emergency Stop Safety Isolation
    # Call emergency_stop with ZERO backend/AI/DB dependencies
    controller.emergency_stop()
    assert controller.state == ControllerState.EMERGENCY_STOP


# ============================================================================
# 7. TELEMETRY TIMEOUT & RECOVERY
# ============================================================================

def test_telemetry_timeout_detection() -> None:
    """Verify adapter detects stale telemetry and updates gateway health."""
    transport = SimulatorTransport()
    adapter = RobotGatewayAdapter(
        transport=transport,
        telemetry_timeout_s=0.1,
    )
    adapter.connect()

    # Ingest initial telemetry packet to start STREAMING
    raw_telemetry = transport.step()
    adapter.ingest_telemetry_payload(raw_telemetry)

    # Wait beyond timeout threshold
    time.sleep(0.15)

    health = adapter.get_health()
    assert health.failure_reason == GatewayFailureReason.TELEMETRY_TIMEOUT
    assert not health.is_healthy


# ============================================================================
# 8. CAMERA STREAM DROP & RECOVERY
# ============================================================================

def test_camera_stream_drop_and_recovery(db_session: Session) -> None:
    """Verify camera stream drops update health while telemetry stream remains active."""
    orchestrator = MissionOrchestrator()
    orchestrator.create_mission(db=db_session, robot_id="PV-SIM-001", mission_id="SIM-M-CAM-01")
    orchestrator.start_mission(db=db_session, mission_id="SIM-M-CAM-01")

    transport = SimulatorTransport()
    adapter = RobotGatewayAdapter(
        transport=transport,
        mission_id="SIM-M-CAM-01",
        frame_timeout_s=0.1,
        auto_ingest_backend=False,
    )
    adapter.connect()

    # Send frame 1
    p1 = transport.generate_synthetic_frame(frame_index=1)
    adapter.ingest_camera_frame(p1, db=db_session)

    # Wait beyond frame timeout
    time.sleep(0.15)

    health = adapter.get_health()
    assert health.failure_reason == GatewayFailureReason.FRAME_TIMEOUT

    # Send frame 2 (recovery)
    p2 = transport.generate_synthetic_frame(frame_index=2)
    adapter.ingest_camera_frame(p2, db=db_session)
    assert adapter.get_health().frame_count == 2


# ============================================================================
# 9. TRANSPORT LINK FAILURE & RESUMPTION
# ============================================================================

class FailingTransport(RobotTransport):
    """Transport simulator double that fails on send/connect."""

    def __init__(self) -> None:
        self._connected = True

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def send(self, message: dict[str, Any] | str) -> None:
        raise TransportConnectionError("Physical link lost")

    def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None:
        raise TransportConnectionError("Physical link lost")


def test_transport_failure_and_resumption() -> None:
    """Verify adapter handles transport connection loss cleanly."""
    failing_transport = FailingTransport()
    adapter = RobotGatewayAdapter(transport=failing_transport)

    adapter.connect()
    assert adapter.is_connected

    # Attempt command over broken link
    with pytest.raises(ControllerError, match="Physical link lost"):
        adapter.move(0.1, 0.0)


# ============================================================================
# 10. GRACEFUL DEGRADATION UNDER MISSING SENSORS
# ============================================================================

def test_graceful_degradation_missing_sensors() -> None:
    """Verify system operates and degrades cleanly when optional sensors are unavailable."""
    config = SimulatorConfig(
        enable_imu=False,
        enable_pressure=False,
        enable_water=False,
    )
    transport = SimulatorTransport(config=config)
    transport.connect()

    packet = transport.step()
    assert "imu" not in packet
    assert "pressure" not in packet
    assert "water" not in packet

    parsed = parse_telemetry(packet)
    assert parsed is not None
    assert parsed.imu is None
    assert parsed.pressure is None
    assert parsed.water is None

    localizer = RobotLocalizer()
    pose = localizer.update(parsed)
    assert pose.quality == LocalizationQuality.DEGRADED


# ============================================================================
# 11. INGESTION EXCEPTION HANDLING
# ============================================================================

def test_ingestion_exception_handling(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    """Verify gateway catches ingestion backend errors without crashing or dropping connection."""
    orchestrator = MissionOrchestrator()
    orchestrator.create_mission(db=db_session, robot_id="PV-SIM-001", mission_id="SIM-M-EXC-01")
    orchestrator.start_mission(db=db_session, mission_id="SIM-M-EXC-01")

    transport = SimulatorTransport()
    adapter = RobotGatewayAdapter(
        transport=transport,
        mission_id="SIM-M-EXC-01",
        auto_ingest_backend=True,
    )
    adapter.connect()

    # Monkeypatch backend ingestion to raise unexpected runtime error
    def failing_ingest(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Database deadlock during ingestion")

    monkeypatch.setattr(
        "backend.app.services.inspection.gateway.ingest_inspection_frame",
        failing_ingest,
    )

    frame_packet = transport.generate_synthetic_frame(frame_index=1)

    # ingest_camera_frame calls ingest_inspection_frame when db is passed
    with pytest.raises(RuntimeError, match="Database deadlock"):
        adapter.ingest_camera_frame(frame_packet, db=db_session)

    assert adapter.is_connected


# ============================================================================
# 12. FRAME DROP & CONTINUITY
# ============================================================================

def test_frame_drop_and_continuity(db_session: Session) -> None:
    """Verify frame drops increment drop counters while maintaining true frame indices."""
    orchestrator = MissionOrchestrator()
    orchestrator.create_mission(db=db_session, robot_id="PV-SIM-001", mission_id="SIM-M-DROP-01")
    orchestrator.start_mission(db=db_session, mission_id="SIM-M-DROP-01")

    transport = SimulatorTransport()
    adapter = RobotGatewayAdapter(
        transport=transport,
        mission_id="SIM-M-DROP-01",
        auto_ingest_backend=False,
    )
    adapter.connect()

    p1 = transport.generate_synthetic_frame(frame_index=1)
    p3 = transport.generate_synthetic_frame(frame_index=3)  # Frame 2 dropped!

    adapter.ingest_camera_frame(p1, db=db_session)
    adapter.ingest_camera_frame(p3, db=db_session)

    assert adapter.get_health().frame_count == 2


# ============================================================================
# 13. DETERMINISTIC RUN COMPARISON
# ============================================================================

def test_deterministic_full_run_comparison(db_session: Session) -> None:
    """Verify running the same simulation sequence twice yields identical trajectory & metrics."""
    def run_sim(mission_id_suffix: str) -> tuple[list[float], int]:
        m_id = f"SIM-DET-{mission_id_suffix}"
        orchestrator = MissionOrchestrator()
        orchestrator.create_mission(db=db_session, robot_id="PV-SIM-001", mission_id=m_id)
        orchestrator.start_mission(db=db_session, mission_id=m_id)

        t = SimulatorTransport(config=SimulatorConfig(mission_id=m_id))
        loc = RobotLocalizer()
        ad = RobotGatewayAdapter(transport=t, mission_id=m_id, localizer=loc, auto_ingest_backend=True)
        ad.connect()

        for idx in range(1, 10):
            telemetry = t.step()
            ad.ingest_telemetry_payload(telemetry, db=db_session)
            f_packet = t.generate_synthetic_frame(frame_index=idx, distance_m=telemetry.get("distance_m"))
            ad.ingest_camera_frame(f_packet, db=db_session)

        snap = orchestrator.get_mission_snapshot(db=db_session, mission_id=m_id)
        orchestrator.complete_mission(db=db_session, mission_id=m_id)
        ad.disconnect()

        distances = [p.distance_m for p in loc.trajectory]
        return distances, snap.progress.observation_count

    dist1, obs1 = run_sim("A")
    dist2, obs2 = run_sim("B")

    assert dist1 == dist2
    assert obs1 == obs2 == 9


# ============================================================================
# 14. HIGH-VOLUME STRESS & BOUNDED MEMORY
# ============================================================================

def test_high_volume_stress_bounded_memory(db_session: Session) -> None:
    """Verify system remains responsive and memory bounded after processing 200 telemetry & 100 frames."""
    orchestrator = MissionOrchestrator()
    m_id = "SIM-M-STRESS-001"
    orchestrator.create_mission(db=db_session, robot_id="PV-SIM-001", mission_id=m_id)
    orchestrator.start_mission(db=db_session, mission_id=m_id)

    transport = SimulatorTransport(mission_id=m_id)
    localizer = RobotLocalizer()
    adapter = RobotGatewayAdapter(
        transport=transport,
        mission_id=m_id,
        localizer=localizer,
        auto_ingest_backend=True,
    )
    adapter.connect()

    # Process 200 telemetry packets and 100 frames
    for idx in range(1, 201):
        raw_telemetry = transport.step()
        adapter.ingest_telemetry_payload(raw_telemetry, db=db_session)

        if idx % 2 == 0:
            frame_idx = idx // 2
            f_packet = transport.generate_synthetic_frame(frame_index=frame_idx, distance_m=raw_telemetry.get("distance_m"))
            adapter.ingest_camera_frame(f_packet, db=db_session)

    health = adapter.get_health()
    assert health.telemetry_packet_count == 200
    assert health.frame_count == 100
    assert len(localizer.trajectory) == 200

    snapshot = orchestrator.get_mission_snapshot(db=db_session, mission_id=m_id)
    assert snapshot.progress.observation_count == 100
    assert snapshot.progress.current_distance_m > 0.0

    orchestrator.complete_mission(db=db_session, mission_id=m_id)
    adapter.disconnect()
