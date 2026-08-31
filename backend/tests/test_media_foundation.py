"""Unit and Integration Tests for Phase 19C.5A Backend Media Foundation.

Tests persistent media snapshots, MJPEG and WebSocket live video streams,
and recording session management (start/stop/status/retrieval).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.app.services.video.frame_store import FrameMetadataStore
from backend.app.services.video.recording import RecordingManager
from backend.app.services.video.snapshot_store import SnapshotStore


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


def create_test_jpeg_bytes(width: int = 100, height: int = 100, color: str = "blue") -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def seeded_mission_frame(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Seed frame metadata and frame image file for mission 'M-MEDIA-TEST'."""
    fs = FrameMetadataStore(tmp_path)
    ss = SnapshotStore(tmp_path)
    rm = RecordingManager(tmp_path)

    monkeypatch.setattr("backend.app.api.video.frame_store", fs)
    monkeypatch.setattr("backend.app.api.video.snapshot_store", ss)
    monkeypatch.setattr("backend.app.api.video.recording_manager", rm)

    img_bytes = create_test_jpeg_bytes()
    fs.save_image(
        mission_id="M-MEDIA-TEST",
        frame_index=0,
        image_bytes=img_bytes,
        extension=".jpg",
    )
    from datetime import datetime, timezone

    from backend.app.services.video.frame_store import FrameMetadata

    fs.append(
        FrameMetadata(
            mission_id="M-MEDIA-TEST",
            frame_index=0,
            timestamp=datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc),
            distance_m=5.5,
            source="webcam",
            frame_path="M-MEDIA-TEST/frame-000000.jpg",
        )
    )
    return fs, ss, rm


# ============================================================================
# SNAPSHOT TESTS
# ============================================================================


def test_create_snapshot_success(api_client: TestClient, seeded_mission_frame) -> None:
    payload = {
        "frame_index": 0,
        "camera_id": "front_cam",
        "notes": "Test structural defect snapshot",
    }
    response = api_client.post(
        "/api/v1/video/missions/M-MEDIA-TEST/snapshots",
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["mission_id"] == "M-MEDIA-TEST"
    assert data["frame_index"] == 0
    assert data["camera_id"] == "front_cam"
    assert data["distance_m"] == 5.5
    assert "snapshot_id" in data
    assert "image_url" in data


def test_create_snapshot_missing_frame(api_client: TestClient, seeded_mission_frame) -> None:
    payload = {"frame_index": 999}
    response = api_client.post(
        "/api/v1/video/missions/M-MEDIA-TEST/snapshots",
        json=payload,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "frame_not_found"


def test_list_and_get_snapshot(api_client: TestClient, seeded_mission_frame) -> None:
    # Create snapshot first
    create_res = api_client.post(
        "/api/v1/video/missions/M-MEDIA-TEST/snapshots",
        json={"frame_index": 0, "camera_id": "cam_01"},
    )
    assert create_res.status_code == 201
    snapshot_id = create_res.json()["snapshot_id"]

    # List snapshots
    list_res = api_client.get("/api/v1/video/missions/M-MEDIA-TEST/snapshots")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["count"] == 1
    assert list_data["snapshots"][0]["snapshot_id"] == snapshot_id

    # Get single snapshot
    get_res = api_client.get(f"/api/v1/video/missions/M-MEDIA-TEST/snapshots/{snapshot_id}")
    assert get_res.status_code == 200
    assert get_res.json()["snapshot_id"] == snapshot_id


def test_get_snapshot_image_binary(api_client: TestClient, seeded_mission_frame) -> None:
    create_res = api_client.post(
        "/api/v1/video/missions/M-MEDIA-TEST/snapshots",
        json={"frame_index": 0},
    )
    snapshot_id = create_res.json()["snapshot_id"]

    img_res = api_client.get(f"/api/v1/video/missions/M-MEDIA-TEST/snapshots/{snapshot_id}/image")
    assert img_res.status_code == 200
    assert len(img_res.content) > 0


def test_delete_snapshot(api_client: TestClient, seeded_mission_frame) -> None:
    create_res = api_client.post(
        "/api/v1/video/missions/M-MEDIA-TEST/snapshots",
        json={"frame_index": 0},
    )
    snapshot_id = create_res.json()["snapshot_id"]

    del_res = api_client.delete(f"/api/v1/video/missions/M-MEDIA-TEST/snapshots/{snapshot_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    get_res = api_client.get(f"/api/v1/video/missions/M-MEDIA-TEST/snapshots/{snapshot_id}")
    assert get_res.status_code == 404


def test_snapshot_path_traversal_prevention(api_client: TestClient, seeded_mission_frame) -> None:
    res = api_client.get("/api/v1/video/missions/../../etc/snapshots/snap-001")
    assert res.status_code in (404, 403, 422)


# ============================================================================
# STREAMING TESTS
# ============================================================================


def test_mjpeg_live_stream_connect(api_client: TestClient, seeded_mission_frame) -> None:
    response = api_client.get(
        "/api/v1/video/missions/M-MEDIA-TEST/stream?loop=false&fps=30.0",
    )
    assert response.status_code == 200
    assert "multipart/x-mixed-replace" in response.headers["content-type"]
    assert b"--frame" in response.content


def test_mjpeg_stream_empty_mission_graceful(api_client: TestClient, seeded_mission_frame) -> None:
    # Mission with 0 frames should yield placeholder stream gracefully
    response = api_client.get(
        "/api/v1/video/missions/M-EMPTY-MISSION/stream?loop=false&fps=30.0",
    )
    assert response.status_code == 200
    assert b"--frame" in response.content


# ============================================================================
# RECORDING SESSION TESTS
# ============================================================================


def test_recording_session_lifecycle(api_client: TestClient, seeded_mission_frame) -> None:
    # 1. Start Recording
    start_res = api_client.post(
        "/api/v1/video/missions/M-RECORD-TEST/recording/start",
        json={"camera_id": "cam_main"},
    )
    assert start_res.status_code == 201
    start_data = start_res.json()
    assert start_data["status"] == "RECORDING"
    recording_id = start_data["recording_id"]

    # 2. Get Status (Active)
    status_res = api_client.get("/api/v1/video/missions/M-RECORD-TEST/recording/status")
    assert status_res.status_code == 200
    assert status_res.json()["is_recording"] is True

    # 3. Duplicate Start Attempt (Conflict 409)
    dup_res = api_client.post(
        "/api/v1/video/missions/M-RECORD-TEST/recording/start",
        json={"camera_id": "cam_main"},
    )
    assert dup_res.status_code == 409

    # 4. Stop Recording
    stop_res = api_client.post(
        f"/api/v1/video/missions/M-RECORD-TEST/recording/stop?recording_id={recording_id}",
    )
    assert stop_res.status_code == 200
    stop_data = stop_res.json()
    assert stop_data["status"] == "STOPPED"
    assert stop_data["stop_time"] is not None

    # 5. Duplicate Stop Attempt (Bad Request 400)
    dup_stop_res = api_client.post(
        "/api/v1/video/missions/M-RECORD-TEST/recording/stop",
    )
    assert dup_stop_res.status_code == 400

    # 6. List Recordings
    list_res = api_client.get("/api/v1/video/missions/M-RECORD-TEST/recordings")
    assert list_res.status_code == 200
    assert list_res.json()["count"] == 1

    # 7. Get Single Recording
    get_res = api_client.get(f"/api/v1/video/missions/M-RECORD-TEST/recordings/{recording_id}")
    assert get_res.status_code == 200
    assert get_res.json()["recording_id"] == recording_id
