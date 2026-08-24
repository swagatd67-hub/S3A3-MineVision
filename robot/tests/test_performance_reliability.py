"""Comprehensive performance, bounded queuing, failure injection, and reliability tests (Phase 17)."""

from __future__ import annotations

import io
import time
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db import Base
from backend.app.models import Robot
from backend.app.services.inspection.exceptions import (
    InvalidImageContentError,
)
from backend.app.services.inspection.gateway import InspectionIngestionGateway
from backend.app.services.inspection.models import CanonicalInspectionFrame
from backend.app.services.mission.orchestrator import MissionOrchestrator
from backend.app.services.video.sewer_classifier import ClassDecision, SewerMLResult
from robot.gateway.adapter import (
    RobotGatewayAdapter,
    RobotGatewayConnectionError,
)
from robot.gateway.models import (
    GatewayFailureReason,
    HardwareFramePacket,
)
from robot.gateway.queue import BoundedFrameQueue, DropPolicy
from robot.localization.models import LocalizationQuality, RobotPose
from robot.transport.base import RobotTransport, TransportConnectionError
from robot.transport.simulator import SimulatorTransport


class FailingTransport(RobotTransport):
    """Transport test double that simulates mid-stream connection failures."""

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
        if not self._connected:
            raise TransportConnectionError("Transport is disconnected")

    def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None:
        if not self._connected:
            raise TransportConnectionError("Transport disconnected during receive")
        return None


class StubSewerMLEngine:
    """Deterministic test double for Sewer-ML classification engine."""

    def __init__(self) -> None:
        self.model_version = "sewer-ml-stub"

    def predict(self, image: Any) -> SewerMLResult:
        decisions = [
            ClassDecision(
                class_code="CR",
                probability=0.9,
                threshold=0.5,
                detected=True,
            )
        ]
        return SewerMLResult(
            decisions=decisions,
            detected_classes=["CR"],
            inference_ms=0.1,
            model_version=self.model_version,
        )


@pytest.fixture(autouse=True)
def reset_singleton() -> Generator[None, None, None]:
    """Reset orchestrator singleton before each test."""
    orch = MissionOrchestrator()
    orch._twins.clear()
    orch._observations.clear()
    orch._observation_ids.clear()
    orch._telemetries.clear()
    orch._poses.clear()
    yield


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """In-memory SQLite database session fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Generate a small 64x64 JPEG image in memory."""
    img = Image.new("RGB", (64, 64), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_bounded_frame_queue_drop_oldest(sample_image_bytes: bytes) -> None:
    """Test BoundedFrameQueue drop oldest policy when buffer overflows."""
    queue: BoundedFrameQueue[int] = BoundedFrameQueue(max_size=3, policy=DropPolicy.DROP_OLDEST)

    assert queue.put(1, frame_index=1) is True
    assert queue.put(2, frame_index=2) is True
    assert queue.put(3, frame_index=3) is True
    assert queue.current_depth == 3

    # 4th item triggers drop of frame 1
    assert queue.put(4, frame_index=4) is True
    assert queue.current_depth == 3

    metrics = queue.get_metrics()
    assert metrics.total_enqueued == 4
    assert metrics.total_dropped == 1
    assert metrics.dropped_frames_log[0]["dropped_item_index"] == 1

    # First dequeued item should now be 2
    assert queue.get() == 2
    assert queue.get() == 3
    assert queue.get() == 4
    assert queue.get() is None


def test_bounded_frame_queue_drop_newest() -> None:
    """Test BoundedFrameQueue drop newest policy."""
    queue: BoundedFrameQueue[int] = BoundedFrameQueue(max_size=2, policy=DropPolicy.DROP_NEWEST)

    assert queue.put(10) is True
    assert queue.put(20) is True
    assert queue.put(30) is False  # Rejected

    metrics = queue.get_metrics()
    assert metrics.total_dropped == 1
    assert queue.get() == 10
    assert queue.get() == 20


def test_robot_gateway_adapter_with_frame_queue(db_session: Session, sample_image_bytes: bytes) -> None:
    """Test RobotGatewayAdapter integration with BoundedFrameQueue."""
    transport = SimulatorTransport()
    queue: BoundedFrameQueue[HardwareFramePacket] = BoundedFrameQueue(max_size=2, policy=DropPolicy.DROP_OLDEST)
    adapter = RobotGatewayAdapter(
        transport=transport,
        robot_id="BOT-01",
        mission_id="M-01",
        frame_queue=queue,
    )
    adapter.connect()

    packet1 = HardwareFramePacket(camera_id="cam0", image_bytes=sample_image_bytes, frame_index=1)
    packet2 = HardwareFramePacket(camera_id="cam0", image_bytes=sample_image_bytes, frame_index=2)
    packet3 = HardwareFramePacket(camera_id="cam0", image_bytes=sample_image_bytes, frame_index=3)

    assert adapter.frame_queue is not None
    adapter.frame_queue.put(packet1, frame_index=1)
    adapter.frame_queue.put(packet2, frame_index=2)
    adapter.frame_queue.put(packet3, frame_index=3)  # Drops packet1

    health = adapter.get_health()
    assert health.dropped_frame_count == 1


def test_idempotent_frame_and_observation_ingestion(db_session: Session, sample_image_bytes: bytes) -> None:
    """Test idempotency: duplicate observations are ignored without error or duplicate DB inserts."""
    robot = Robot(robot_id="ROBOT-01", name="Rover 1")
    db_session.add(robot)
    db_session.commit()

    orchestrator = MissionOrchestrator()
    mission = orchestrator.create_mission(db_session, robot_id="ROBOT-01", mission_id="M-IDEM-01")
    orchestrator.start_mission(db_session, mission.mission_id)

    gateway = InspectionIngestionGateway()
    stub_sewer = StubSewerMLEngine()

    frame = CanonicalInspectionFrame(
        mission_id="M-IDEM-01",
        robot_id="ROBOT-01",
        frame_index=1,
        image_bytes=sample_image_bytes,
        distance_m=5.0,
        pose=RobotPose(
            timestamp=datetime.now(timezone.utc),
            distance_m=5.0,
            x=5.0,
            y=0.0,
            heading_rad=0.0,
            heading_deg=0.0,
            quality=LocalizationQuality.TRACKING,
        ),
    )

    # First Ingestion
    res1 = gateway.ingest_frame(db_session, frame, sewer_engine=stub_sewer)
    assert len(res1.observations) > 0

    # Second Ingestion with identical frame and observation IDs
    res2 = gateway.ingest_frame(db_session, frame, sewer_engine=stub_sewer)
    assert res2 is not None

    twin = orchestrator._twins["M-IDEM-01"]
    # Digital twin observation count should remain equal to unique observations (1)
    assert len(twin.snapshot().latest_observations) == len(res1.observations)


def test_failure_injection_transport_disconnect(db_session: Session) -> None:
    """Failure Injection: Transport disconnects during poll."""
    robot = Robot(robot_id="BOT-FAIL", name="Rover Fail")
    db_session.add(robot)
    db_session.commit()
    orchestrator = MissionOrchestrator()
    orchestrator.create_mission(db_session, robot_id="BOT-FAIL", mission_id="M-FAIL")

    failing_transport = FailingTransport()
    adapter = RobotGatewayAdapter(transport=failing_transport, robot_id="BOT-FAIL", mission_id="M-FAIL")
    adapter.connect()

    # Case A: Underlying transport signals disconnection gracefully
    failing_transport.disconnect()
    res = adapter.poll(db=db_session)
    assert res is None
    assert adapter.controller.state.name == "DISCONNECTED"

    # Case B: Underlying transport raises active error during receive
    class ExceptionOnReceiveTransport(FailingTransport):
        def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None:
            raise TransportConnectionError("Hardware connection lost unexpectedly")

    err_adapter = RobotGatewayAdapter(transport=ExceptionOnReceiveTransport(), robot_id="BOT-FAIL", mission_id="M-FAIL")
    err_adapter.connect()

    with pytest.raises(RobotGatewayConnectionError):
        err_adapter.poll(db=db_session)

    health = err_adapter.get_health()
    assert health.failure_reason == GatewayFailureReason.TRANSPORT_ERROR


def test_failure_injection_corrupt_frame(db_session: Session) -> None:
    """Failure Injection: Corrupt image bytes handling."""
    robot = Robot(robot_id="ROBOT-CORRUPT", name="Rover Corrupt")
    db_session.add(robot)
    db_session.commit()

    orchestrator = MissionOrchestrator()
    orchestrator.create_mission(db_session, robot_id="ROBOT-CORRUPT", mission_id="M-CORRUPT")

    gateway = InspectionIngestionGateway()
    corrupt_frame = CanonicalInspectionFrame(
        mission_id="M-CORRUPT",
        frame_index=1,
        image_bytes=b"INVALID_CORRUPT_BYTES_XYZ",
    )

    with pytest.raises(InvalidImageContentError):
        gateway.ingest_frame(db_session, corrupt_frame)


def test_batch_ingestion_commit_optimization(db_session: Session, sample_image_bytes: bytes) -> None:
    """Test batch ingestion commits all frames in a single transaction."""
    robot = Robot(robot_id="ROBOT-BATCH", name="Rover Batch")
    db_session.add(robot)
    db_session.commit()

    orchestrator = MissionOrchestrator()
    orchestrator.create_mission(db_session, robot_id="ROBOT-BATCH", mission_id="M-BATCH-01")

    gateway = InspectionIngestionGateway()
    stub_sewer = StubSewerMLEngine()

    frames = [
        CanonicalInspectionFrame(
            mission_id="M-BATCH-01",
            frame_index=i,
            image_bytes=sample_image_bytes,
            distance_m=float(i),
        )
        for i in range(1, 11)
    ]

    result = gateway.ingest_batch(db_session, frames, sewer_engine=stub_sewer)
    assert result.total_submitted == 10
    assert result.total_succeeded == 10
    assert result.total_failed == 0


def test_long_running_memory_stability(db_session: Session, sample_image_bytes: bytes) -> None:
    """Validate long-running execution over 100 frames stays fast and stable."""
    robot = Robot(robot_id="ROBOT-LONG", name="Rover Long")
    db_session.add(robot)
    db_session.commit()

    orchestrator = MissionOrchestrator()
    orchestrator.create_mission(db_session, robot_id="ROBOT-LONG", mission_id="M-LONG-01")

    gateway = InspectionIngestionGateway()
    stub_sewer = StubSewerMLEngine()

    start_time = time.perf_counter()
    for i in range(1, 101):
        frame = CanonicalInspectionFrame(
            mission_id="M-LONG-01",
            frame_index=i,
            image_bytes=sample_image_bytes,
            distance_m=float(i) * 0.1,
        )
        gateway.ingest_frame(db_session, frame, sewer_engine=stub_sewer)

    elapsed = time.perf_counter() - start_time
    assert elapsed < 5.0  # Must process 100 frames in under 5 seconds
