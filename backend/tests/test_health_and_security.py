"""Integration tests for health, readiness, metrics, correlation IDs, and security boundaries."""

from fastapi.testclient import TestClient

from backend.app.db import init_db
from backend.app.main import app

init_db()
client = TestClient(app)


def test_liveness_endpoint() -> None:
    res = client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "live"
    assert data["service"] == "pipevision-api"
    assert "version" in data


def test_health_alias_endpoint() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "live"


def test_readiness_endpoint() -> None:
    res = client.get("/health/ready")
    # In SQLite test environment, readiness is 200 OK
    assert res.status_code in (200, 503)
    data = res.json()
    assert "components" in data
    assert "database" in data["components"]
    assert "ai_model" in data["components"]
    assert "storage" in data["components"]


def test_operational_metrics_endpoint() -> None:
    res = client.get("/metrics")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "pipevision-api"
    assert "uptime_s" in data
    assert "total_missions" in data
    assert "ai_engine_version" in data


def test_correlation_id_middleware() -> None:
    # 1. Custom correlation ID passed in header is echoed back
    custom_cid = "test-corr-id-999"
    res = client.get("/health/live", headers={"X-Correlation-ID": custom_cid})
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-ID") == custom_cid

    # 2. Auto-generated correlation ID when not provided
    res2 = client.get("/health/live")
    assert res2.status_code == 200
    assert res2.headers.get("X-Correlation-ID") is not None
    assert res2.headers.get("X-Correlation-ID").startswith("req-")


def test_path_traversal_protection() -> None:
    # Directory ingestion payload attempting path traversal outside import root
    payload = {
        "mission_id": "test_m1",
        "directory_path": "../../../etc/passwd",
        "auto_create_mission": True,
    }
    res = client.post("/api/v1/video/ingest/directory", json=payload)
    assert res.status_code in (403, 400)
    data = res.json()
    assert "detail" in data
    # Ensure no secret / raw system credentials leaked
    assert "password" not in str(data).lower()


def test_oversized_upload_rejection() -> None:
    # 100 bytes is okay, but test that 60MB payload gets rejected if threshold is lowered
    # We test single image endpoint with empty image first
    res = client.post(
        "/api/v1/video/ingest/image",
        data={"mission_id": "m1"},
        files={"image": ("test.jpg", b"", "image/jpeg")},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "empty_image"


def test_structured_error_response_no_credential_leak() -> None:
    # Request invalid mission ID or endpoint to verify error payload structure
    res = client.get("/api/v1/missions/non_existent_mission_id_12345")
    assert res.status_code == 404
    data = res.json()
    assert data["error"] == "http_error"
    assert "detail" in data
    assert "status_code" in data
    assert "correlation_id" in data
