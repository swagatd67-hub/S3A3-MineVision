"""Comprehensive Unit Tests for Robot Telemetry Layer."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from robot.telemetry import (
    IMUData,
    PressureData,
    RobotTelemetry,
    TelemetryManager,
    TelemetryManagerStatus,
    TelemetryParseError,
    TelemetryValidationError,
    WaterQualityData,
    parse_telemetry,
)
from robot.transport.simulator import SimulatorTransport


def test_valid_complete_telemetry_dict() -> None:
    raw = {
        "robot_id": "PV-001",
        "mission_id": "MISSION-100",
        "timestamp": "2026-08-21T20:00:00Z",
        "battery_percent": 85.5,
        "distance_m": 12.34,
        "body_diameter_mm": 110.0,
        "state": "INSPECTING",
        "imu": {
            "ax": 0.01,
            "ay": -0.02,
            "az": 9.81,
            "gx": 0.05,
            "gy": 0.02,
            "gz": -0.01,
        },
        "pressure": {
            "body_kpa": 98.5,
            "front_anchor_kpa": 170.0,
            "rear_anchor_kpa": 165.0,
        },
        "water": {
            "temperature_c": 24.5,
            "ph": 7.1,
            "conductivity_ms_cm": 1.5,
            "turbidity_ntu": 25.0,
        },
    }

    t = parse_telemetry(raw)
    assert isinstance(t, RobotTelemetry)
    assert t.robot_id == "PV-001"
    assert t.mission_id == "MISSION-100"
    assert t.timestamp == datetime(2026, 8, 21, 20, 0, 0, tzinfo=timezone.utc)
    assert t.battery_percent == 85.5
    assert t.distance_m == 12.34
    assert t.body_diameter_mm == 110.0
    assert t.state == "INSPECTING"

    assert isinstance(t.imu, IMUData)
    assert t.imu.ax == 0.01
    assert t.imu.az == 9.81

    assert isinstance(t.pressure, PressureData)
    assert t.pressure.body_kpa == 98.5

    assert isinstance(t.water, WaterQualityData)
    assert t.water.ph == 7.1


def test_valid_json_telemetry_string() -> None:
    raw_dict = {
        "robot_id": "PV-JSON-01",
        "timestamp": "2026-08-21T12:00:00+00:00",
        "battery_percent": 90.0,
    }
    raw_json = json.dumps(raw_dict)

    t = parse_telemetry(raw_json)
    assert isinstance(t, RobotTelemetry)
    assert t.robot_id == "PV-JSON-01"
    assert t.battery_percent == 90.0


def test_none_telemetry() -> None:
    assert parse_telemetry(None) is None


def test_malformed_json_string() -> None:
    raw_json = "{bad_json: 123"
    with pytest.raises(TelemetryParseError, match="Malformed JSON"):
        parse_telemetry(raw_json)


def test_missing_required_fields() -> None:
    # Missing robot_id
    raw = {"battery_percent": 50.0}
    with pytest.raises(TelemetryValidationError, match="robot_id"):
        parse_telemetry(raw)


def test_invalid_field_types() -> None:
    # robot_id not a string
    with pytest.raises(TelemetryValidationError, match="robot_id"):
        parse_telemetry({"robot_id": 12345})

    # battery_percent string instead of float
    with pytest.raises(TelemetryValidationError, match="battery_percent"):
        parse_telemetry({"robot_id": "PV-1", "battery_percent": "ninety"})


def test_invalid_timestamp() -> None:
    # Invalid date string
    with pytest.raises(TelemetryValidationError, match="timestamp"):
        parse_telemetry({"robot_id": "PV-1", "timestamp": "not-a-date"})


def test_imu_parsing_validation() -> None:
    # Valid IMU
    raw = {
        "robot_id": "PV-IMU",
        "imu": {"ax": 0.1, "ay": 0.2, "az": 9.8, "gx": 0.0, "gy": 0.0, "gz": 0.1},
    }
    t = parse_telemetry(raw)
    assert t is not None
    assert t.imu is not None
    assert t.imu.ax == 0.1

    # Invalid IMU field type
    bad_imu = {
        "robot_id": "PV-IMU",
        "imu": {"ax": "high", "ay": 0.2, "az": 9.8, "gx": 0.0, "gy": 0.0, "gz": 0.1},
    }
    with pytest.raises(TelemetryValidationError, match="ax"):
        parse_telemetry(bad_imu)


def test_pressure_parsing() -> None:
    raw = {
        "robot_id": "PV-PRESS",
        "pressure": {"body_kpa": 101.3, "front_anchor_kpa": 150.0},
    }
    t = parse_telemetry(raw)
    assert t is not None
    assert t.pressure is not None
    assert t.pressure.body_kpa == 101.3
    assert t.pressure.front_anchor_kpa == 150.0
    assert t.pressure.rear_anchor_kpa is None


def test_water_sensor_parsing() -> None:
    raw = {
        "robot_id": "PV-WATER",
        "water": {"temperature_c": 20.0, "ph": 7.0},
    }
    t = parse_telemetry(raw)
    assert t is not None
    assert t.water is not None
    assert t.water.temperature_c == 20.0
    assert t.water.ph == 7.0
    assert t.water.turbidity_ntu is None


def test_battery_bounds() -> None:
    # Negative battery
    with pytest.raises(TelemetryValidationError, match="battery_percent"):
        parse_telemetry({"robot_id": "PV-BAT", "battery_percent": -5.0})

    # Battery > 100
    with pytest.raises(TelemetryValidationError, match="battery_percent"):
        parse_telemetry({"robot_id": "PV-BAT", "battery_percent": 105.0})


def test_distance_handling() -> None:
    # Negative distance
    with pytest.raises(TelemetryValidationError, match="distance_m"):
        parse_telemetry({"robot_id": "PV-DIST", "distance_m": -10.0})


def test_parser_does_not_mutate_original_dict() -> None:
    raw = {
        "robot_id": "PV-MUTATE",
        "battery_percent": 80.0,
        "imu": {"ax": 0.0, "ay": 0.0, "az": 9.81, "gx": 0.0, "gy": 0.0, "gz": 0.0},
    }
    raw_copy = json.loads(json.dumps(raw))
    parse_telemetry(raw)
    assert raw == raw_copy


def test_parser_rejects_command_dictionary() -> None:
    command_payload = {"name": "MOVE", "arguments": {"linear": 0.5, "angular": 0.0}}
    with pytest.raises(TelemetryValidationError, match="command payload"):
        parse_telemetry(command_payload)


def test_simulator_telemetry_compatibility() -> None:
    sim = SimulatorTransport(robot_id="PV-SIM-COMPAT")
    sim.connect()

    step_packet = sim.step()
    t = parse_telemetry(step_packet)
    assert isinstance(t, RobotTelemetry)
    assert t.robot_id == "PV-SIM-COMPAT"
    assert t.imu is not None
    assert t.imu.az == 9.81
    assert t.pressure is not None
    assert t.water is not None

    recv_packet = sim.receive(timeout=0.1)
    t2 = parse_telemetry(recv_packet)
    assert isinstance(t2, RobotTelemetry)
    assert t2.robot_id == "PV-SIM-COMPAT"

    sim.disconnect()


def test_telemetry_manager_freshness_and_staleness() -> None:
    mgr = TelemetryManager()
    assert mgr.status == TelemetryManagerStatus.NO_DATA
    assert mgr.is_stale(timeout_seconds=2.0)
    assert not mgr.is_fresh(timeout_seconds=2.0)

    now = datetime.now(timezone.utc)
    raw = {"robot_id": "PV-MGR", "timestamp": now.isoformat()}
    mgr.process_raw(raw, receive_time=now)

    assert mgr.status == TelemetryManagerStatus.TELEMETRY_RECEIVED
    assert mgr.latest_telemetry is not None
    assert mgr.latest_telemetry.robot_id == "PV-MGR"
    assert mgr.last_received_at == now
    assert mgr.is_fresh(timeout_seconds=2.0, current_time=now)

    # 5 seconds later
    future_time = now + timedelta(seconds=5)
    assert mgr.is_stale(timeout_seconds=2.0, current_time=future_time)
    assert not mgr.is_fresh(timeout_seconds=2.0, current_time=future_time)


def test_telemetry_manager_poll_and_simulator() -> None:
    sim = SimulatorTransport(robot_id="PV-MGR-SIM")
    sim.connect()

    mgr = TelemetryManager(sim)
    t = mgr.poll()

    assert isinstance(t, RobotTelemetry)
    assert t.robot_id == "PV-MGR-SIM"
    assert mgr.status == TelemetryManagerStatus.TELEMETRY_RECEIVED
    assert mgr.latest_telemetry == t

    sim.disconnect()
    assert mgr.poll() is None
    assert mgr.status == TelemetryManagerStatus.TRANSPORT_DISCONNECTED


def test_repeated_telemetry_updates() -> None:
    mgr = TelemetryManager()
    for i in range(5):
        raw = {"robot_id": "PV-REP", "distance_m": float(i)}
        mgr.process_raw(raw)
        assert mgr.latest_telemetry is not None
        assert mgr.latest_telemetry.distance_m == float(i)
