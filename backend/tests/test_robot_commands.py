"""Unit & integration tests for FastAPI Robot Command endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.robot.manager import robot_manager

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_robot_manager():
    yield
    robot_manager.disconnect_all()


def test_robot_command_move_accepted():
    response = client.post(
        "/api/v1/robots/ROV-TEST-01/command",
        json={"name": "MOVE", "arguments": {"linear": 0.5, "angular": 0.1}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["robot_id"] == "ROV-TEST-01"
    assert data["command"] == "MOVE"
    assert data["status"] == "accepted"
    assert data["controller_state"] in ("MOVING", "IDLE")


def test_robot_command_stop_accepted():
    # Move first
    client.post(
        "/api/v1/robots/ROV-TEST-01/command",
        json={"name": "MOVE", "arguments": {"linear": 0.5, "angular": 0.0}},
    )
    # Stop
    response = client.post(
        "/api/v1/robots/ROV-TEST-01/command",
        json={"name": "STOP"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["command"] == "STOP"
    assert data["controller_state"] == "IDLE"


def test_robot_command_camera_pan_accepted():
    response = client.post(
        "/api/v1/robots/ROV-TEST-01/command",
        json={"name": "CAMERA_PAN", "arguments": {"angle_deg": 45.0}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["command"] == "CAMERA_PAN"


def test_robot_command_invalid_name():
    response = client.post(
        "/api/v1/robots/ROV-TEST-01/command",
        json={"name": "FLY_TO_MOON"},
    )
    assert response.status_code == 422
    assert "Unsupported command" in response.json()["detail"]


def test_robot_command_speed_limit_exceeded():
    response = client.post(
        "/api/v1/robots/ROV-TEST-01/command",
        json={"name": "MOVE", "arguments": {"linear": 10.0, "angular": 0.0}},
    )
    assert response.status_code == 422
    assert "exceeds maximum allowed speed" in response.json()["detail"]


def test_robot_estop_and_subsequent_move_rejection():
    # E-Stop endpoint
    estop_resp = client.post("/api/v1/robots/ROV-TEST-01/estop")
    assert estop_resp.status_code == 200
    data = estop_resp.json()
    assert data["command"] == "EMERGENCY_STOP"
    assert data["controller_state"] == "EMERGENCY_STOP"

    # Repeated E-Stop is idempotent
    repeated_resp = client.post("/api/v1/robots/ROV-TEST-01/estop")
    assert repeated_resp.status_code == 200

    # Move attempt should be rejected with 409 Conflict
    move_resp = client.post(
        "/api/v1/robots/ROV-TEST-01/command",
        json={"name": "MOVE", "arguments": {"linear": 0.2, "angular": 0.0}},
    )
    assert move_resp.status_code == 409
    assert "EMERGENCY_STOP state" in move_resp.json()["detail"]
