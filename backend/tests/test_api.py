from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health():
    r = client.get('/health'); assert r.status_code == 200

def test_robot_registration():
    payload = {"robot_id":"PV-TEST-001","name":"Simulator","capabilities":["camera","imu","water_quality"]}
    r = client.post('/api/v1/robots/register', json=payload)
    assert r.status_code == 200
    assert r.json()['status'] == 'registered'

def test_telemetry():
    payload = {"robot_id":"PV-TEST-001","battery_percent":82,"distance_m":4.2,"state":"INSPECTING",
               "imu":{"ax":0.0,"ay":0.0,"az":9.81,"gx":0.1,"gy":0.0,"gz":0.2}}
    r = client.post('/api/v1/telemetry', json=payload)
    assert r.status_code == 200

def test_mission_creation():
    r = client.post('/api/v1/missions', json={"robot_id":"PV-TEST-001","objective":"INSPECT_AND_CLEAN"})
    assert r.status_code == 201
    assert r.json()['status'] == 'CREATED'
