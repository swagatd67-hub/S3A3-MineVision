import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.db import init_db
from backend.app.main import app

init_db()
client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_robot_registration():
    payload = {
        "robot_id": "PV-TEST-001",
        "name": "Simulator",
        "capabilities": ["camera", "imu", "water_quality"],
    }
    r = client.post("/api/v1/robots/register", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "registered"


def test_telemetry():
    payload = {
        "robot_id": "PV-TEST-001",
        "battery_percent": 82,
        "distance_m": 4.2,
        "state": "INSPECTING",
        "imu": {"ax": 0.0, "ay": 0.0, "az": 9.81, "gx": 0.1, "gy": 0.0, "gz": 0.2},
    }
    r = client.post("/api/v1/telemetry", json=payload)
    assert r.status_code == 200


def test_mission_creation():
    r = client.post(
        "/api/v1/missions",
        json={"robot_id": "PV-TEST-001", "objective": "INSPECT_AND_CLEAN"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "CREATED"


def test_classify_sewer_frame_api_missing_frame():
    r = client.post("/api/v1/video/missions/M-MISSING/frames/999/classify_sewer")
    assert r.status_code == 404
    assert r.json()["detail"] == "frame_not_found"


def test_classify_sewer_frame_api_missing_image_file():
    payload = {
        "mission_id": "M-NO-IMAGE",
        "frame_index": 1,
        "timestamp": "2026-08-19T12:00:00Z",
        "distance_m": 5.0,
        "source": "webcam",
        "frame_path": None,
    }
    r_store = client.post("/api/v1/video/frames", json=payload)
    assert r_store.status_code == 201

    r_classify = client.post(
        "/api/v1/video/missions/M-NO-IMAGE/frames/1/classify_sewer"
    )
    assert r_classify.status_code == 404
    assert r_classify.json()["detail"] == "frame_not_found"


def test_classify_sewer_frame_api_success(tmp_path, monkeypatch):
    import json

    import torch

    from backend.app.services.video.sewer_classifier import (
        reset_sewer_classifier_engine,
    )
    from backend.app.services.video.sewer_dataset import DEFECT_CLASSES
    from backend.app.services.video.sewer_model import SewerDefectClassifier

    model = SewerDefectClassifier(num_classes=17, pretrained=False)
    checkpoint_path = tmp_path / "dummy_checkpoint.pt"
    thresholds_path = tmp_path / "dummy_thresholds.json"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "classes": DEFECT_CLASSES,
        },
        checkpoint_path,
    )

    thresholds_data = {cls_code: 0.5 for cls_code in DEFECT_CLASSES}
    thresholds_path.write_text(json.dumps(thresholds_data), encoding="utf-8")

    monkeypatch.setenv("SEWER_CHECKPOINT_PATH", str(checkpoint_path))
    monkeypatch.setenv("SEWER_THRESHOLDS_PATH", str(thresholds_path))
    reset_sewer_classifier_engine()

    img = np.full((120, 160, 3), fill_value=128, dtype=np.uint8)
    _, buffer = cv2.imencode(".jpg", img)

    r_img = client.post(
        "/api/v1/video/frames/image",
        data={
            "mission_id": "M-SEWER-001",
            "frame_index": "42",
            "timestamp": "2026-08-19T12:00:00Z",
            "distance_m": "12.5",
            "source": "webcam",
        },
        files={"image": ("test.jpg", buffer.tobytes(), "image/jpeg")},
    )
    assert r_img.status_code == 201

    r_classify = client.post(
        "/api/v1/video/missions/M-SEWER-001/frames/42/classify_sewer"
    )
    assert r_classify.status_code == 200
    data = r_classify.json()

    assert data["mission_id"] == "M-SEWER-001"
    assert data["frame_index"] == 42
    assert data["model_version"] == "sewer-ml-e009"
    assert data["inference_ms"] > 0
    assert isinstance(data["detected_classes"], list)
    assert len(data["decisions"]) == 17

    first_dec = data["decisions"][0]
    assert "class_code" in first_dec
    assert "probability" in first_dec
    assert "threshold" in first_dec
    assert "detected" in first_dec

    reset_sewer_classifier_engine()
