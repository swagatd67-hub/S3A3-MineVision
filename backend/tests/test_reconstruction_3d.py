"""Unit tests for 3D Pipe Reconstruction API & deterministic generator service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base, get_db
from backend.app.main import app
from backend.app.models import InspectionObservationRow, Mission
from backend.app.services.mission.exceptions import MissionNotFoundError
from backend.app.services.reconstruction_3d import generate_3d_reconstruction


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test_recon.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
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


def test_reconstruction_3d_mission_not_found(db_session):
    with pytest.raises(MissionNotFoundError):
        generate_3d_reconstruction(db_session, "M-NON-EXISTENT-999")


def test_reconstruction_3d_deterministic_generation(db_session):
    mission = Mission(
        mission_id="M-TEST-3D",
        robot_id="ROV-01",
        objective="3D_TEST",
        status="CREATED",
    )
    db_session.add(mission)
    db_session.commit()

    res1 = generate_3d_reconstruction(db_session, "M-TEST-3D")
    res2 = generate_3d_reconstruction(db_session, "M-TEST-3D")

    assert res1.mission_id == "M-TEST-3D"
    assert res1.total_length_m == res2.total_length_m
    assert res1.reconstructed_length_m == res2.reconstructed_length_m
    assert len(res1.sections) == len(res2.sections)
    assert len(res1.defects) == len(res2.defects)


def test_reconstruction_3d_with_real_observations(db_session):
    mission = Mission(
        mission_id="M-TEST-OBS-3D",
        robot_id="ROV-01",
        objective="3D_OBS_TEST",
        status="INSPECTING",
    )
    db_session.add(mission)

    obs = InspectionObservationRow(
        observation_id="OBS-TEST-3D-001",
        mission_id="M-TEST-OBS-3D",
        frame_index=10,
        distance_m=18.5,
        class_code="CRACK",
        confidence=0.88,
        box={"x1": 0.2, "y1": 0.2, "x2": 0.4, "y2": 0.4},
    )
    db_session.add(obs)
    db_session.commit()

    res = generate_3d_reconstruction(db_session, "M-TEST-OBS-3D")
    assert res.mission_id == "M-TEST-OBS-3D"
    assert len(res.defects) >= 1

    defect = next(d for d in res.defects if d.id == "OBS-TEST-3D-001")
    assert defect.class_code == "CRACK"
    assert defect.distance_m == 18.5
    assert defect.confidence == 0.88
    assert defect.clock_angle_deg > 0.0


def test_reconstruction_3d_api_endpoint(api_client, db_session):
    mission = Mission(
        mission_id="M-TEST-API-3D",
        robot_id="ROV-01",
        objective="API_TEST",
        status="COMPLETED",
    )
    db_session.add(mission)
    db_session.commit()

    r = api_client.get("/api/v1/missions/M-TEST-API-3D/reconstruction3d")
    assert r.status_code == 200
    data = r.json()

    assert data["mission_id"] == "M-TEST-API-3D"
    assert data["progress_percent"] == 100.0
    assert "sections" in data
    assert "defects" in data
    assert "centerline" in data


def test_reconstruction_3d_api_404(api_client):
    r = api_client.get("/api/v1/missions/M-INVALID-RECON-99/reconstruction3d")
    assert r.status_code == 404
    assert r.json()["detail"] == "Mission not found"

