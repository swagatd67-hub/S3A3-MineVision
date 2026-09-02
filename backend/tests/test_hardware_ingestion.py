"""Tests for ESP32-CAM background hardware frame ingestion service and API endpoints."""

from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.app.services.video.hardware_ingestion import (
    HardwareIngestionManager,
)
from backend.app.services.video.source import ESP32CAMSource

client = TestClient(app)


def generate_valid_test_jpeg() -> bytes:
    buf = BytesIO()
    img = Image.new("RGB", (320, 240), color="blue")
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
async def reset_hardware_manager(monkeypatch: pytest.MonkeyPatch):
    from backend.app.config import Settings
    mock_settings = Settings(
        camera_source_type="esp32cam",
        esp32_cam_url="http://192.168.137.180:81/stream",
        esp32_cam_snapshot_url="http://192.168.137.180/capture",
    )
    monkeypatch.setattr("backend.app.services.video.hardware_ingestion.get_settings", lambda: mock_settings)
    monkeypatch.setattr("backend.app.config.get_settings", lambda: mock_settings)
    await HardwareIngestionManager.reset_instance_async()
    yield
    await HardwareIngestionManager.reset_instance_async()


@pytest.mark.anyio
async def test_hardware_ingestion_worker_start_stop():
    manager = HardwareIngestionManager.get_instance()
    status = manager.start_worker("M-TEST-01", camera_id="cam-01", fps=10.0)
    assert status.mission_id == "M-TEST-01"
    assert status.is_ingesting is True

    # Stop worker
    stopped_status = await manager.stop_worker("M-TEST-01", camera_id="cam-01")
    assert stopped_status.is_ingesting is False


@pytest.mark.anyio
async def test_hardware_ingestion_prevents_duplicate_worker():
    manager = HardwareIngestionManager.get_instance()
    status1 = manager.start_worker("M-TEST-02", camera_id="cam-01", fps=5.0)
    status2 = manager.start_worker("M-TEST-02", camera_id="cam-01", fps=5.0)
    assert status1.mission_id == status2.mission_id
    assert status2.is_ingesting is True

    await manager.stop_worker("M-TEST-02", camera_id="cam-01")


@pytest.mark.anyio
async def test_hardware_ingestion_missing_checkpoint_null_engine(monkeypatch: pytest.MonkeyPatch):
    manager = HardwareIngestionManager.get_instance()
    test_jpeg = generate_valid_test_jpeg()

    # Mock fetch_snapshot to return valid JPEG bytes
    monkeypatch.setattr(ESP32CAMSource, "fetch_snapshot", lambda _self: test_jpeg)

    status = manager.start_worker("M-TEST-03", camera_id="cam-01", fps=50.0)
    assert status.inference_available is False  # Missing checkpoint best.pt

    # Let the loop execute ticks
    await asyncio.sleep(0.3)

    current_status = manager.get_status("M-TEST-03", camera_id="cam-01")
    assert current_status.frame_count >= 1
    assert current_status.camera_connected is True

    await manager.stop_worker("M-TEST-03", camera_id="cam-01")


@pytest.mark.anyio
async def test_hardware_ingestion_esp32_disconnect_handled(monkeypatch: pytest.MonkeyPatch):
    manager = HardwareIngestionManager.get_instance()

    # Mock fetch_snapshot to return None (disconnect/timeout)
    monkeypatch.setattr(ESP32CAMSource, "fetch_snapshot", lambda _self: None)

    manager.start_worker("M-TEST-04", camera_id="cam-01", fps=50.0)
    await asyncio.sleep(0.05)

    status = manager.get_status("M-TEST-04", camera_id="cam-01")
    assert status.camera_connected is False
    assert status.last_error is not None

    await manager.stop_worker("M-TEST-04", camera_id="cam-01")


@pytest.mark.anyio
async def test_hardware_ingestion_api_endpoints(monkeypatch: pytest.MonkeyPatch):
    test_jpeg = generate_valid_test_jpeg()
    monkeypatch.setattr(ESP32CAMSource, "fetch_snapshot", lambda _self: test_jpeg)

    # 1. Start Capture
    resp = client.post("/api/v1/video/missions/M-TEST-API/capture/start", json={"fps": 5.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mission_id"] == "M-TEST-API"
    assert data["is_ingesting"] is True

    # 2. Get Status
    resp = client.get("/api/v1/video/missions/M-TEST-API/capture/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mission_id"] == "M-TEST-API"

    # 3. Stop Capture
    resp = client.post("/api/v1/video/missions/M-TEST-API/capture/stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_ingesting"] is False
