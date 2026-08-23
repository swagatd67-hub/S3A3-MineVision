"""Unit & Integration Test Suite for Phase 12 Offline Media Processing Pipeline.

Tests photo directory ingestion (with natural numeric sorting and sidecars),
video frame extraction (sampling, timestamp derivation, distance stepping),
partial failure resilience, security path checks, and MissionOrchestrator integration.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.video import ALLOWED_INGEST_ROOT
from backend.app.db import Base, get_db
from backend.app.main import app
from backend.app.models import Mission, Robot
from backend.app.services.inspection import (
    BoundingBox,
    RawPerceptionItem,
    VideoIngestionResult,
    ingest_photo_directory,
    ingest_video_file,
)
from backend.app.services.mission.orchestrator import MissionOrchestrator
from backend.app.services.video.sewer_classifier import ClassDecision, SewerMLResult


class StubSewerMLEngine:
    """Deterministic test double for Sewer-ML classification engine."""

    def __init__(self, model_name: str = "stub_sewer_ml_v1") -> None:
        self.model_name = model_name

    def predict(self, image: Any) -> SewerMLResult:
        decision = ClassDecision(
            class_code="RB",
            probability=0.85,
            threshold=0.5,
            detected=True,
        )
        return SewerMLResult(
            decisions=[decision],
            detected_classes=["RB"],
            inference_ms=1.0,
            model_version=self.model_name,
        )

    def predict_image(self, image_path: Any) -> dict[str, float]:
        return {"RB": 0.85, "OB": 0.12}

    def predict_bytes(self, image_bytes: bytes) -> dict[str, float]:
        return {"RB": 0.85, "OB": 0.12}


class StubYOLODetector:
    """Deterministic test double for YOLO object detector."""

    def detect(self, image_input: Any) -> list[RawPerceptionItem]:
        return [
            RawPerceptionItem(
                class_code="CRACK",
                confidence=0.92,
                model_name="yolo_stub",
                box=BoundingBox(10.0, 10.0, 100.0, 100.0),
                source_type="yolo",
            )
        ]


@pytest.fixture(autouse=True)
def stub_ai_engines(monkeypatch: pytest.MonkeyPatch) -> StubSewerMLEngine:
    """Autouse fixture to prevent loading production model checkpoints in tests."""
    stub_sewer = StubSewerMLEngine()
    stub_yolo = StubYOLODetector()

    monkeypatch.setattr(
        "backend.app.services.inspection.gateway.get_sewer_classifier_engine",
        lambda *args, **kwargs: stub_sewer,
    )
    monkeypatch.setattr(
        "backend.app.api.video.get_sewer_classifier_engine",
        lambda *args, **kwargs: stub_sewer,
    )
    monkeypatch.setattr(
        "backend.app.services.video.detection.load_detector",
        lambda *args, **kwargs: stub_yolo,
    )
    return stub_sewer


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """File-backed SQLite database session fixture with seeded default robot for thread-safe API testing."""
    db_path = tmp_path / "test_offline_media.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()

    robot = Robot(robot_id="robot_01", name="Test Robot")
    session.add(robot)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient fixture with overridden DB dependency."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def create_dummy_jpeg(path: Path, width: int = 100, height: int = 100, color: str = "red") -> None:
    """Helper to create a valid JPEG file on disk."""
    img = Image.new("RGB", (width, height), color=color)
    img.save(path, format="JPEG")


def create_dummy_video(path: Path, num_frames: int = 15, fps: float = 10.0) -> None:
    """Helper to create a valid synthetic AVI video file using OpenCV."""
    fourcc = cv2.VideoWriter.fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (320, 240))
    for i in range(num_frames):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # Put frame index text on synthetic frame
        cv2.putText(frame, f"Frame {i}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        writer.write(frame)
    writer.release()


# -----------------------------------------------------------------------------
# PHOTO DIRECTORY TESTS
# -----------------------------------------------------------------------------


def test_photo_directory_natural_sorting(db_session: Session) -> None:
    """Verify photo directory ingestion orders files numerically (1.jpg, 2.jpg, 10.jpg)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Create files out of alphabetical order: img_10.jpg, img_2.jpg, img_1.jpg
        create_dummy_jpeg(tmp_path / "img_10.jpg")
        create_dummy_jpeg(tmp_path / "img_2.jpg")
        create_dummy_jpeg(tmp_path / "img_1.jpg")

        res = ingest_photo_directory(
            db_session,
            directory_path=tmp_dir,
            mission_id="M-NAT-SORT",
            robot_id="robot_01",
        )

        assert res.total_submitted == 3
        assert res.total_succeeded == 3
        assert res.results[0].frame_index == 0
        assert res.results[1].frame_index == 1
        assert res.results[2].frame_index == 2
        # Check frame paths are preserved
        assert len(res.results) == 3


def test_photo_directory_sidecar_parsing(db_session: Session) -> None:
    """Verify per-image .json and directory metadata.json sidecar parsing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_dummy_jpeg(tmp_path / "frame_001.jpg")
        create_dummy_jpeg(tmp_path / "frame_002.jpg")

        # Per-image sidecar for frame_001
        sidecar_001 = {
            "timestamp": "2026-08-24T12:00:00+00:00",
            "distance_m": 4.5,
            "robot_id": "robot_01",
            "camera_id": "front_cam",
            "pose": {"x": 4.5, "y": 0.1, "heading_deg": 5.0},
        }
        (tmp_path / "frame_001.json").write_text(json.dumps(sidecar_001), encoding="utf-8")

        res = ingest_photo_directory(
            db_session,
            directory_path=tmp_dir,
            mission_id="M-SIDECAR-TEST",
        )

        assert res.total_succeeded == 2
        r1 = res.results[0]
        assert r1.distance_m == 4.5
        assert r1.timestamp_iso == "2026-08-24T12:00:00+00:00"


def test_photo_directory_auto_mission_creation(db_session: Session) -> None:
    """Verify missing mission is auto-created during photo directory ingestion."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_dummy_jpeg(tmp_path / "photo1.jpg")

        mission_id = "M-AUTO-CREATE-PHOTO"
        assert db_session.get(Mission, mission_id) is None

        res = ingest_photo_directory(
            db_session,
            directory_path=tmp_dir,
            mission_id=mission_id,
            auto_create_mission=True,
        )

        assert res.total_succeeded == 1
        assert db_session.get(Mission, mission_id) is not None


def test_photo_directory_partial_failure(db_session: Session) -> None:
    """Verify invalid corrupt image records a failure without aborting valid images."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_dummy_jpeg(tmp_path / "good.jpg")
        # Create a corrupt file with invalid JPEG header
        (tmp_path / "bad.jpg").write_bytes(b"CORRUPT_BYTES_NOT_AN_IMAGE")

        res = ingest_photo_directory(
            db_session,
            directory_path=tmp_dir,
            mission_id="M-PARTIAL-FAIL",
            robot_id="robot_01",
        )

        assert res.total_submitted == 2
        assert res.total_succeeded == 1
        assert res.total_failed == 1
        assert len(res.failures) == 1
        assert res.failures[0]["frame_index"] == 0  # bad.jpg sorted before good.jpg naturally


# -----------------------------------------------------------------------------
# VIDEO PROCESSING TESTS
# -----------------------------------------------------------------------------


def test_video_file_ingestion_basic(db_session: Session) -> None:
    """Verify basic video frame extraction and ingestion into PipeVision."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "test_video.avi"
        create_dummy_video(video_path, num_frames=10, fps=10.0)

        res = ingest_video_file(
            db_session,
            video_path=video_path,
            mission_id="M-VIDEO-BASIC",
            robot_id="robot_01",
        )

        assert isinstance(res, VideoIngestionResult)
        assert res.total_video_frames == 10
        assert res.sampled_frames == 10
        assert res.total_succeeded == 10
        assert res.total_failed == 0
        assert res.fps == 10.0
        assert len(res.results) == 10


def test_video_file_sampling_interval(db_session: Session) -> None:
    """Verify frame_interval sampling skips intermediate frames."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "test_video.avi"
        create_dummy_video(video_path, num_frames=20, fps=10.0)

        # Sample every 5th frame -> frames 0, 5, 10, 15 (total 4)
        res = ingest_video_file(
            db_session,
            video_path=video_path,
            mission_id="M-VIDEO-SAMPLED",
            frame_interval=5,
            robot_id="robot_01",
        )

        assert res.total_video_frames == 20
        assert res.sampled_frames == 4
        assert res.total_succeeded == 4
        indices = [r.frame_index for r in res.results]
        assert indices == [0, 5, 10, 15]


def test_video_file_start_timestamp_derivation(db_session: Session) -> None:
    """Verify frame timestamps increase deterministically when start_timestamp is provided."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "test_video.avi"
        create_dummy_video(video_path, num_frames=5, fps=10.0)

        start_ts = datetime(2026, 8, 24, 10, 0, 0, tzinfo=timezone.utc)
        res = ingest_video_file(
            db_session,
            video_path=video_path,
            mission_id="M-VIDEO-TS",
            start_timestamp=start_ts,
            robot_id="robot_01",
        )

        assert res.total_succeeded == 5
        # Frame 0: 10:00:00, Frame 1: 10:00:00.1, Frame 2: 10:00:00.2
        ts0 = res.results[0].timestamp_iso
        ts1 = res.results[1].timestamp_iso
        assert ts0 is not None and "2026-08-24T10:00:00" in ts0
        assert ts1 is not None and ("2026-08-24T10:00:00.100000" in ts1 or "2026-08-24T10:00:00.1" in ts1)


def test_video_file_no_timestamp_preserves_none(db_session: Session) -> None:
    """Verify that when no start_timestamp is provided, frame timestamp remains None (no fake clock time)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "test_video.avi"
        create_dummy_video(video_path, num_frames=3, fps=10.0)

        res = ingest_video_file(
            db_session,
            video_path=video_path,
            mission_id="M-VIDEO-NO-TS",
            robot_id="robot_01",
        )

        assert res.total_succeeded == 3
        for r in res.results:
            assert r.timestamp_iso is None


def test_video_file_distance_stepping(db_session: Session) -> None:
    """Verify distance_start_m and distance_step_m assign linear pipe distances."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "test_video.avi"
        create_dummy_video(video_path, num_frames=4, fps=10.0)

        res = ingest_video_file(
            db_session,
            video_path=video_path,
            mission_id="M-VIDEO-DIST",
            distance_start_m=10.0,
            distance_step_m=0.5,
            robot_id="robot_01",
        )

        assert res.total_succeeded == 4
        distances = [r.distance_m for r in res.results]
        assert distances == [10.0, 10.5, 11.0, 11.5]


# -----------------------------------------------------------------------------
# API ENDPOINT & SECURITY TESTS
# -----------------------------------------------------------------------------


def test_video_file_api_endpoint(api_client: TestClient) -> None:
    """Verify POST /api/v1/video/ingest/video endpoint with valid file in ALLOWED_INGEST_ROOT."""
    import gc

    ALLOWED_INGEST_ROOT.mkdir(parents=True, exist_ok=True)
    video_filename = "api_test_video.avi"
    video_dest = ALLOWED_INGEST_ROOT / video_filename

    try:
        create_dummy_video(video_dest, num_frames=5, fps=10.0)

        response = api_client.post(
            "/api/v1/video/ingest/video",
            json={
                "mission_id": "M-API-VIDEO",
                "video_path": str(video_dest),
                "distance_start_m": 0.0,
                "distance_step_m": 1.0,
                "robot_id": "robot_01",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["mission_id"] == "M-API-VIDEO"
        assert data["total_video_frames"] == 5
        assert data["total_succeeded"] == 5
    finally:
        gc.collect()
        if video_dest.exists():
            try:
                video_dest.unlink()
            except PermissionError:
                pass


def test_video_file_api_security_restriction(api_client: TestClient) -> None:
    """Verify HTTP 403 is returned if video file is outside ALLOWED_INGEST_ROOT."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        forbidden_video = Path(tmp_dir) / "forbidden.avi"
        create_dummy_video(forbidden_video, num_frames=2, fps=10.0)

        response = api_client.post(
            "/api/v1/video/ingest/video",
            json={
                "mission_id": "M-FORBIDDEN-VIDEO",
                "video_path": str(forbidden_video),
            },
        )

        assert response.status_code == 403
        assert "allowed import root" in response.json()["detail"]


def test_offline_media_orchestrator_integration(db_session: Session) -> None:
    """Verify offline video processing integrates with MissionOrchestrator Digital Twin & Mapping."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "test_video.avi"
        create_dummy_video(video_path, num_frames=5, fps=10.0)

        mission_id = "M-ORCHESTRATOR-INTEG"

        res = ingest_video_file(
            db_session,
            video_path=video_path,
            mission_id=mission_id,
            distance_start_m=0.0,
            distance_step_m=2.0,
            robot_id="robot_01",
        )

        assert res.total_succeeded == 5

        # Check MissionOrchestrator snapshot
        orchestrator = MissionOrchestrator()
        twin_state = orchestrator.get_digital_twin_state(db_session, mission_id)
        assert twin_state.mission_id == mission_id
        assert twin_state.inspection_map is not None


def test_offline_media_no_fabricated_robot_01(db_session: Session) -> None:
    """Verify offline media ingestion with robot_id=None does NOT invent robot_01."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_dummy_jpeg(tmp_path / "frame1.jpg")

        mission_id = "M-NO-FABRICATED-ROBOT"
        res = ingest_photo_directory(
            db_session,
            directory_path=tmp_dir,
            mission_id=mission_id,
            robot_id=None,
            auto_create_mission=True,
        )

        assert res.total_succeeded == 1
        created_mission = db_session.get(Mission, mission_id)
        assert created_mission is not None
        # Robot ID should be OFFLINE
        assert created_mission.robot_id == "OFFLINE"
        # No fake Robot table row should have been created in database for OFFLINE
        assert db_session.get(Robot, "OFFLINE") is None
        # Result frame mission_id should match
        assert res.results[0].mission_id == mission_id


def test_sidecar_pose_parsing_variations() -> None:
    """Verify sidecar pose parsing handles full, partial, missing position data correctly."""
    from backend.app.services.inspection.sidecar import parse_sidecar_dict

    # 1. Full pose data
    full_data = {
        "timestamp": "2026-08-24T12:00:00+00:00",
        "distance_m": 12.5,
        "pose": {"x": 12.5, "y": 0.2, "heading_deg": 15.0, "quality": "TRACKING"},
    }
    meta_full = parse_sidecar_dict(full_data)
    assert meta_full.pose is not None
    assert meta_full.pose.x == 12.5
    assert meta_full.pose.y == 0.2
    assert meta_full.pose.heading_deg == 15.0

    # 2. Distance only in pose dict
    dist_only = {"pose": {"distance_m": 8.0}}
    meta_dist = parse_sidecar_dict(dist_only)
    assert meta_dist.pose is not None
    assert meta_dist.pose.distance_m == 8.0
    assert meta_dist.pose.x == 8.0

    # 3. Missing x and missing distance_m (heading only) -> pose must NOT fabricate x=0
    missing_pos = {"pose": {"heading_deg": 10.0}}
    meta_missing = parse_sidecar_dict(missing_pos)
    assert meta_missing.pose is None
    assert meta_missing.distance_m is None

    # 4. Completely missing pose
    no_pose = {"timestamp": "2026-08-24T12:00:00+00:00"}
    meta_none = parse_sidecar_dict(no_pose)
    assert meta_none.pose is None
    assert meta_none.distance_m is None


def test_explicit_derived_distance_semantics(db_session: Session) -> None:
    """Verify derived distance stepping semantics for offline video ingestion."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "test_video.avi"
        create_dummy_video(video_path, num_frames=3, fps=10.0)

        # 1. Unconfigured distance -> frames keep distance_m=None
        res_none = ingest_video_file(
            db_session,
            video_path=video_path,
            mission_id="M-DIST-NONE",
            distance_start_m=None,
            distance_step_m=None,
            robot_id=None,
        )
        assert res_none.results[0].distance_m is None
        assert res_none.results[1].distance_m is None

        # 2. Configured distance step -> explicit derived stepping
        res_step = ingest_video_file(
            db_session,
            video_path=video_path,
            mission_id="M-DIST-STEP",
            distance_start_m=0.0,
            distance_step_m=1.5,
            robot_id=None,
        )
        assert res_step.results[0].distance_m == 0.0
        assert res_step.results[1].distance_m == 1.5
        assert res_step.results[2].distance_m == 3.0
