"""Unit and Integration Tests for Phase 11: Ingestion Gateway."""

import io
from datetime import datetime, timezone

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base, get_db
from backend.app.main import app
from backend.app.models import InspectionObservationRow, Robot
from backend.app.services.inspection import (
    CanonicalInspectionFrame,
    InvalidImageContentError,
    ingest_inspection_batch,
    ingest_inspection_frame,
    ingest_photo_directory,
)
from backend.app.services.inspection.gateway import (
    extract_exif_timestamp,
    resolve_frame_id,
    resolve_timestamp,
)
from backend.app.services.mission.exceptions import MissionNotFoundError
from backend.app.services.mission.orchestrator import MissionOrchestrator
from backend.app.services.video.sewer_classifier import ClassDecision, SewerMLResult
from robot.localization.models import LocalizationQuality, RobotPose


class StubSewerMLEngine:
    """Deterministic test double for Sewer-ML classification engine."""

    def __init__(self, detected_classes: list[str] | None = None) -> None:
        self.detected_classes = detected_classes if detected_classes is not None else ["CR"]
        self.model_version = "sewer-ml-stub"

    def predict(self, image: np.ndarray) -> SewerMLResult:
        if image is None or image.size == 0:
            raise ValueError("image must be a non-empty numpy array")

        decisions = [
            ClassDecision(
                class_code="CR",
                probability=0.95 if "CR" in self.detected_classes else 0.05,
                threshold=0.5,
                detected="CR" in self.detected_classes,
            )
        ]
        return SewerMLResult(
            decisions=decisions,
            detected_classes=[c for c in self.detected_classes if c in self.detected_classes],
            inference_ms=1.0,
            model_version=self.model_version,
        )


@pytest.fixture(autouse=True)
def stub_ai_engines(monkeypatch):
    """Inject deterministic test doubles for Sewer-ML engine across all Phase 11 gateway and API tests."""
    stub_engine = StubSewerMLEngine()
    monkeypatch.setattr(
        "backend.app.services.inspection.gateway.get_sewer_classifier_engine",
        lambda *args, **kwargs: stub_engine,
    )
    monkeypatch.setattr(
        "backend.app.api.video.get_sewer_classifier_engine",
        lambda *args, **kwargs: stub_engine,
    )
    return stub_engine


def create_test_image_bytes(
    width: int = 100,
    height: int = 100,
    color: str = "red",
    fmt: str = "JPEG",
    exif_dt: str | None = None,
) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    if exif_dt:
        exif = img.getexif()
        exif[36867] = exif_dt  # DateTimeOriginal tag ID 36867
        img.save(buf, format=fmt, exif=exif)
    else:
        img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test_gateway.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Seed test robot in database
    robot = Robot(robot_id="robot_01", name="Robot 01")
    db.add(robot)
    db.commit()

    # Reset orchestrator singleton state and create mission via real orchestrator path
    orchestrator = MissionOrchestrator()
    orchestrator._observations.clear()
    orchestrator._observation_ids.clear()
    orchestrator._twins.clear()
    orchestrator._telemetries.clear()
    orchestrator._poses.clear()
    orchestrator.create_mission(db, mission_id="test-mission-01", robot_id="robot_01", objective="INSPECT")

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def api_client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ============================================================================
# 1. Deterministic Frame ID Tests
# ============================================================================

def test_deterministic_frame_id_preserves_custom_id():
    fid = resolve_frame_id(mission_id="m1", frame_index=0, provided_frame_id="custom-frame-123")
    assert fid == "custom-frame-123"


def test_deterministic_frame_id_reproducible_generation():
    img_bytes = create_test_image_bytes()
    id1 = resolve_frame_id(mission_id="m1", frame_index=5, image_bytes=img_bytes)
    id2 = resolve_frame_id(mission_id="m1", frame_index=5, image_bytes=img_bytes)
    assert id1 == id2
    assert id1.startswith("frame-000005-")


# ============================================================================
# 2. Capture Timestamp Semantics Tests
# ============================================================================

def test_resolve_timestamp_explicit_prioritized():
    dt_exp = datetime(2026, 8, 24, 10, 0, 0, tzinfo=timezone.utc)
    res = resolve_timestamp(dt_exp)
    assert res == dt_exp


def test_resolve_timestamp_exif_fallback():
    img_bytes = create_test_image_bytes(exif_dt="2026:08:24 12:34:56")
    exif_parsed = extract_exif_timestamp(img_bytes)
    assert exif_parsed == datetime(2026, 8, 24, 12, 34, 56, tzinfo=timezone.utc)
    res = resolve_timestamp(explicit_ts=None, image_bytes=img_bytes)
    assert res == datetime(2026, 8, 24, 12, 34, 56, tzinfo=timezone.utc)


def test_resolve_timestamp_unavailable_when_missing():
    img_bytes = create_test_image_bytes()
    res = resolve_timestamp(explicit_ts=None, image_bytes=img_bytes)
    assert res is None


# ============================================================================
# 3. Single Image Ingestion Tests (Level 1, 2, 3)
# ============================================================================

def test_single_image_ingestion_level_1_no_location(db_session):
    img_bytes = create_test_image_bytes()
    frame = CanonicalInspectionFrame(
        mission_id="test-mission-01",
        frame_index=0,
        image_bytes=img_bytes,
        source="photo",
        distance_m=None,
        pose=None,
    )

    result = ingest_inspection_frame(db_session, frame)

    assert result.mission_id == "test-mission-01"
    assert result.distance_m is None
    assert result.frame_path is not None
    assert len(result.observations) > 0

    for obs in result.observations:
        assert obs.distance_m is None
        assert obs.robot_pose is None
        assert obs.localization_quality == "UNAVAILABLE"


def test_single_image_ingestion_level_2_with_distance(db_session):
    img_bytes = create_test_image_bytes()
    frame = CanonicalInspectionFrame(
        mission_id="test-mission-01",
        frame_index=1,
        image_bytes=img_bytes,
        source="photo",
        distance_m=12.5,
        pose=None,
    )

    result = ingest_inspection_frame(db_session, frame)

    assert result.distance_m == 12.5
    for obs in result.observations:
        assert obs.distance_m == 12.5
        assert obs.robot_pose is None
        assert obs.localization_quality == "UNAVAILABLE"


def test_single_image_ingestion_level_3_with_pose_and_telemetry(db_session):
    img_bytes = create_test_image_bytes()
    pose = RobotPose(
        timestamp=None,
        distance_m=15.0,
        x=15.0,
        y=0.2,
        heading_rad=0.05,
        heading_deg=2.86,
        quality=LocalizationQuality.TRACKING,
        source="slam",
    )

    frame = CanonicalInspectionFrame(
        mission_id="test-mission-01",
        frame_index=2,
        image_bytes=img_bytes,
        source="photo",
        distance_m=15.0,
        pose=pose,
    )

    result = ingest_inspection_frame(db_session, frame)

    assert result.distance_m == 15.0
    for obs in result.observations:
        assert obs.distance_m == 15.0
        assert obs.robot_pose is not None
        assert obs.robot_pose.x == 15.0
        assert obs.localization_quality == "TRACKING"


def test_single_image_ingestion_mission_not_found(db_session):
    img_bytes = create_test_image_bytes()
    frame = CanonicalInspectionFrame(
        mission_id="non-existent-mission",
        frame_index=0,
        image_bytes=img_bytes,
    )

    with pytest.raises(MissionNotFoundError):
        ingest_inspection_frame(db_session, frame)


def test_single_image_ingestion_invalid_image_type(db_session):
    frame = CanonicalInspectionFrame(
        mission_id="test-mission-01",
        frame_index=0,
        image_bytes=b"NOT_AN_IMAGE_DATA",
    )

    with pytest.raises(InvalidImageContentError):
        ingest_inspection_frame(db_session, frame)


# ============================================================================
# 4. Batch Photo Ingestion & Partial Failure Tests
# ============================================================================

def test_batch_ingestion_all_valid(db_session):
    img1 = create_test_image_bytes(color="red")
    img2 = create_test_image_bytes(color="blue")
    img3 = create_test_image_bytes(color="green")

    frames = [
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=0, image_bytes=img1, distance_m=1.0),
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=1, image_bytes=img2, distance_m=2.0),
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=2, image_bytes=img3, distance_m=3.0),
    ]

    res = ingest_inspection_batch(db_session, frames)

    assert res.total_submitted == 3
    assert res.total_succeeded == 3
    assert res.total_failed == 0
    assert len(res.results) == 3
    assert res.results[0].frame_index == 0
    assert res.results[1].frame_index == 1
    assert res.results[2].frame_index == 2


def test_batch_ingestion_partial_failure(db_session):
    img_valid = create_test_image_bytes()
    frames = [
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=0, image_bytes=img_valid),
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=1, image_bytes=b"CORRUPTED_BYTES"),
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=2, image_bytes=img_valid),
    ]

    res = ingest_inspection_batch(db_session, frames)

    assert res.total_submitted == 3
    assert res.total_succeeded == 2
    assert res.total_failed == 1
    assert len(res.failures) == 1
    assert res.failures[0]["frame_index"] == 1


def test_batch_commit_empty_batch(db_session):
    res = ingest_inspection_batch(db_session, [])
    assert res.total_submitted == 0
    assert res.total_succeeded == 0
    assert res.total_failed == 0
    assert res.results == []


def test_batch_commit_failure_rollback(db_session, monkeypatch):
    img1 = create_test_image_bytes(color="red")
    frames = [
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=0, image_bytes=img1),
    ]

    # Force commit failure on db
    def failing_commit():
        raise RuntimeError("Simulated DB Disk Write Error")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    res = ingest_inspection_batch(db_session, frames)

    assert res.total_succeeded == 0
    assert res.total_failed == 1
    assert res.failures[0]["error_type"] == "BatchCommitError"
    assert "Simulated DB Disk Write Error" in res.failures[0]["error"]


# ============================================================================
# 5. Offline Directory Workflow Tests & Security Checks
# ============================================================================

def test_photo_directory_ingestion(db_session, tmp_path):
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    p1 = photos_dir / "0001.jpg"
    p2 = photos_dir / "0002.png"
    p1.write_bytes(create_test_image_bytes(fmt="JPEG"))
    p2.write_bytes(create_test_image_bytes(fmt="PNG"))

    res = ingest_photo_directory(
        db_session,
        directory_path=photos_dir,
        mission_id="test-mission-01",
        distance_step_m=0.5,
    )

    assert res.total_submitted == 2
    assert res.total_succeeded == 2
    assert res.results[0].distance_m == 0.0
    assert res.results[1].distance_m == 0.5


def test_directory_ingestion_security_path_rejection(api_client):
    response = api_client.post(
        "/api/v1/video/ingest/directory",
        json={
            "mission_id": "test-mission-01",
            "directory_path": "../../../etc/passwd",
        },
    )
    assert response.status_code == 403
    assert "allowed import root" in response.json()["detail"]


# ============================================================================
# 6. Mission Orchestration & Persistence Verification
# ============================================================================

def test_observation_persistence_and_digital_twin(db_session):
    img_bytes = create_test_image_bytes()
    frame = CanonicalInspectionFrame(
        mission_id="test-mission-01",
        frame_index=0,
        image_bytes=img_bytes,
        distance_m=5.0,
    )

    res = ingest_inspection_frame(db_session, frame, sewer_engine=StubSewerMLEngine())
    assert len(res.observations) > 0

    # Verify DB persistence
    rows = db_session.query(InspectionObservationRow).filter_by(mission_id="test-mission-01").all()
    assert len(rows) > 0

    # Verify Digital Twin snapshot update
    orchestrator = MissionOrchestrator()
    twin_state = orchestrator.get_digital_twin_state(db_session, "test-mission-01")
    assert twin_state is not None
    assert len(twin_state.latest_observations) > 0


# ============================================================================
# 7. API Route Integration Tests
# ============================================================================

def test_api_ingest_single_image_success(api_client):
    img_bytes = create_test_image_bytes()
    files = {"image": ("test.jpg", img_bytes, "image/jpeg")}
    data = {
        "mission_id": "test-mission-01",
        "distance_m": "10.0",
        "source": "photo",
    }

    response = api_client.post("/api/v1/video/ingest/image", data=data, files=files)
    assert response.status_code == 201
    payload = response.json()
    assert payload["mission_id"] == "test-mission-01"
    assert payload["distance_m"] == 10.0
    assert "observations" in payload


def test_api_ingest_batch_success(api_client):
    img1 = create_test_image_bytes(color="red")
    img2 = create_test_image_bytes(color="blue")
    files = [
        ("images", ("img1.jpg", img1, "image/jpeg")),
        ("images", ("img2.jpg", img2, "image/jpeg")),
    ]
    data = {
        "mission_id": "test-mission-01",
        "distance_start_m": "0.0",
        "distance_step_m": "1.0",
    }

    response = api_client.post("/api/v1/video/ingest/batch", data=data, files=files)
    assert response.status_code == 201
    payload = response.json()
    assert payload["total_submitted"] == 2
    assert payload["total_succeeded"] == 2


# ============================================================================
# 8. Provenance & Semantic Distance Preservation Tests
# ============================================================================

def test_single_photo_without_robot_camera_and_distance(db_session):
    img_bytes = create_test_image_bytes()
    frame = CanonicalInspectionFrame(
        mission_id="test-mission-01",
        frame_index=0,
        image_bytes=img_bytes,
        source="photo",
    )
    assert frame.robot_id is None
    assert frame.camera_id is None
    assert frame.distance_m is None

    result = ingest_inspection_frame(db_session, frame)
    assert result.distance_m is None
    for obs in result.observations:
        assert obs.distance_m is None


def test_batch_photos_without_robot_camera_and_distance(db_session):
    img1 = create_test_image_bytes(color="red")
    img2 = create_test_image_bytes(color="blue")
    frames = [
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=0, image_bytes=img1),
        CanonicalInspectionFrame(mission_id="test-mission-01", frame_index=1, image_bytes=img2),
    ]
    for f in frames:
        assert f.robot_id is None
        assert f.camera_id is None
        assert f.distance_m is None

    res = ingest_inspection_batch(db_session, frames)
    assert res.total_succeeded == 2
    for item in res.results:
        assert item.distance_m is None


def test_directory_photos_without_robot_camera_and_distance(db_session, tmp_path):
    photos_dir = tmp_path / "photos_no_meta"
    photos_dir.mkdir()
    (photos_dir / "0001.jpg").write_bytes(create_test_image_bytes(fmt="JPEG"))
    (photos_dir / "0002.png").write_bytes(create_test_image_bytes(fmt="PNG"))

    res = ingest_photo_directory(
        db_session,
        directory_path=photos_dir,
        mission_id="test-mission-01",
    )
    assert res.total_succeeded == 2
    for item in res.results:
        assert item.distance_m is None


def test_explicit_robot_camera_and_distance_preserved(db_session):
    img_bytes = create_test_image_bytes()
    frame = CanonicalInspectionFrame(
        mission_id="test-mission-01",
        robot_id="actual-robot",
        camera_id="front-camera",
        frame_index=0,
        image_bytes=img_bytes,
        distance_m=42.5,
    )
    assert frame.robot_id == "actual-robot"
    assert frame.camera_id == "front-camera"
    assert frame.distance_m == 42.5

    res = ingest_inspection_frame(db_session, frame)
    assert res.distance_m == 42.5
    for obs in res.observations:
        assert obs.distance_m == 42.5
