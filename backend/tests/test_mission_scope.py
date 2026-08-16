from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.main import app


def test_mission_created_for_registered_robot():
    client = TestClient(app)
    robot_id = "PV-MISSION-TEST"

    reg = client.post(
        "/api/v1/robots/register",
        json={
            "robot_id": robot_id,
            "name": "Mission Test Robot",
            "capabilities": ["camera", "imu"],
        },
    )
    assert reg.status_code == 200

    mission = client.post(
        "/api/v1/missions",
        json={"robot_id": robot_id, "objective": "INSPECT"},
    )
    assert mission.status_code == 201
    body = mission.json()
    assert body["robot_id"] == robot_id
    assert body["status"] == "CREATED"


def test_telemetry_can_be_scoped_to_mission():
    client = TestClient(app)
    robot_id = "PV-MISSION-TELEM-TEST"

    client.post(
        "/api/v1/robots/register",
        json={
            "robot_id": robot_id,
            "name": "Telemetry Mission Test",
            "capabilities": ["imu"],
        },
    )
    mission = client.post(
        "/api/v1/missions",
        json={"robot_id": robot_id, "objective": "INSPECT"},
    ).json()
    mission_id = mission["mission_id"]

    telemetry = client.post(
        "/api/v1/telemetry",
        json={
            "robot_id": robot_id,
            "mission_id": mission_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "distance_m": 1.2,
            "battery_percent": 99.0,
            "state": "INSPECTING",
        },
    )
    assert telemetry.status_code == 200
    assert telemetry.json()["mission_id"] == mission_id

    mission_rows = client.get(f"/api/v1/telemetry/mission/{mission_id}")
    assert mission_rows.status_code == 200
    assert len(mission_rows.json()) >= 1

    analytics = client.get(f"/api/v1/analytics/missions/{mission_id}")
    assert analytics.status_code == 200
    assert analytics.json()["mission_id"] == mission_id
    assert analytics.json()["robot_id"] == robot_id
