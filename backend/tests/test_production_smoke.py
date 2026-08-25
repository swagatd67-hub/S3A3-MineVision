"""Deterministic production smoke test for PipeVision backend and AI perception pipeline."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.config import get_settings, reset_settings
from backend.app.db import check_database_connection
from backend.app.main import app
from backend.app.services.video.sewer_classifier import get_sewer_classifier_engine

client = TestClient(app)


def _create_synthetic_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (224, 224), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_production_smoke_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Full end-to-end production smoke test."""
    monkeypatch.setenv("ALLOW_NULL_SEWER_ENGINE", "true")
    reset_settings()

    # 1. Config Validation
    settings = get_settings()
    settings.validate_environment()
    assert settings.environment in ("development", "test", "production")

    # 2. DB Readiness
    db_ok, db_msg = check_database_connection()
    assert db_ok is True
    assert "connected" in db_msg.lower()

    # 3. AI Engine Readiness
    sewer_engine = get_sewer_classifier_engine(allow_null_fallback=True)
    assert sewer_engine is not None
    assert hasattr(sewer_engine, "model_version")

    # 4. API Liveness and Readiness Probes
    live_res = client.get("/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "live"

    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"

    # 5. Create Test Mission via API
    # Ensure robot registered first
    client.post(
        "/api/v1/robots/register",
        json={"robot_id": "SMOKE_ROBOT_01", "name": "Smoke Bot", "firmware_version": "1.0"},
    )

    mission_payload = {
        "robot_id": "SMOKE_ROBOT_01",
        "objective": "INSPECT",
        "notes": "Production smoke test mission",
    }

    create_res = client.post("/api/v1/missions", json=mission_payload)
    assert create_res.status_code == 201
    mission_data = create_res.json()
    mission_id = mission_data["mission_id"]
    assert mission_id is not None

    # Start mission
    start_res = client.post(f"/api/v1/missions/{mission_id}/start")
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "RUNNING"

    # 6. Ingest Test Image Frame
    jpeg_bytes = _create_synthetic_jpeg_bytes()
    ingest_res = client.post(
        "/api/v1/video/ingest/image",
        data={
            "mission_id": mission_id,
            "robot_id": "SMOKE_ROBOT_01",
            "source": "smoke_test",
            "frame_index": "0",
            "distance_m": "5.0",
        },
        files={"image": ("smoke_frame_0.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert ingest_res.status_code == 201
    ingest_data = ingest_res.json()
    assert ingest_data["mission_id"] == mission_id
    assert ingest_data["frame_index"] == 0
    assert ingest_data["distance_m"] == 5.0

    # 7. Read Persisted Observations
    obs_res = client.get(f"/api/v1/missions/{mission_id}/observations")
    assert obs_res.status_code == 200
    obs_data = obs_res.json()
    assert obs_data["mission_id"] == mission_id
    assert isinstance(obs_data["observations"], list)

    # 8. Complete Mission
    complete_res = client.post(f"/api/v1/missions/{mission_id}/complete")
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "COMPLETED"

    # 9. Verify Operational Metrics
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert metrics_data["total_missions"] >= 1

    reset_settings()
