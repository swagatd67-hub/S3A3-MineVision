"""Unit tests for generic local gas sensor generator and telemetry integration."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.config import Settings, load_settings_from_env, reset_settings
from backend.app.schemas.telemetry import GasSensorData, TelemetryPacket
from backend.app.services.gas_sensor import (
    GasSensorGenerator,
    GasSensorService,
    classify_gas_status,
)


def test_gas_status_classification():
    """Verify application-level gas status thresholds."""
    assert classify_gas_status(0.0) == "NORMAL"
    assert classify_gas_status(39.9) == "NORMAL"
    assert classify_gas_status(40.0) == "ELEVATED"
    assert classify_gas_status(69.9) == "ELEVATED"
    assert classify_gas_status(70.0) == "HIGH"
    assert classify_gas_status(89.9) == "HIGH"
    assert classify_gas_status(90.0) == "CRITICAL"
    assert classify_gas_status(100.0) == "CRITICAL"


def test_gas_sensor_generator_bounds_and_smoothness():
    """Verify generator output is bounded and varies smoothly."""
    generator = GasSensorGenerator(min_val=0.0, max_val=100.0, initial_val=30.0)

    previous_val = 30.0
    for _ in range(50):
        reading = generator.next_reading()
        val = reading["value"]
        status = reading["status"]

        assert 0.0 <= val <= 100.0
        assert status == classify_gas_status(val)
        assert reading["sensor_id"] == "gas-01"
        assert reading["sensor_type"] == "gas"
        assert reading["source"] == "local_simulator"

        # Smoothness check: change between consecutive readings should be bounded
        delta = abs(val - previous_val)
        assert delta <= 5.0, f"Abrupt jump detected: delta={delta}"
        previous_val = val


def test_gas_sensor_config_toggle(monkeypatch: pytest.MonkeyPatch):
    """Verify gas sensor settings parsing from environment."""
    reset_settings()
    monkeypatch.setenv("GAS_SENSOR_ENABLED", "false")
    monkeypatch.setenv("GAS_SENSOR_INTERVAL_S", "2.0")
    monkeypatch.setenv("GAS_SENSOR_MIN", "10.0")
    monkeypatch.setenv("GAS_SENSOR_MAX", "80.0")

    settings = load_settings_from_env()
    assert settings.gas_sensor_enabled is False
    assert settings.gas_sensor_interval_s == 2.0
    assert settings.gas_sensor_min == 10.0
    assert settings.gas_sensor_max == 80.0
    reset_settings()


def test_telemetry_packet_gas_serialization():
    """Verify TelemetryPacket correctly serializes optional gas data."""
    gas = GasSensorData(
        sensor_id="gas-01",
        sensor_type="gas",
        value=42.5,
        status="ELEVATED",
        source="local_simulator",
    )
    packet = TelemetryPacket(robot_id="ROV-01", state="IDLE", gas=gas)
    dumped = packet.model_dump(mode="json")

    assert dumped["robot_id"] == "ROV-01"
    assert dumped["gas"]["value"] == 42.5
    assert dumped["gas"]["status"] == "ELEVATED"
    assert dumped["gas"]["source"] == "local_simulator"


def test_telemetry_packet_backward_compatibility():
    """Verify TelemetryPacket works without gas data."""
    packet = TelemetryPacket(robot_id="ROV-01", state="IDLE")
    dumped = packet.model_dump(mode="json")

    assert dumped["robot_id"] == "ROV-01"
    assert dumped["gas"] is None


@pytest.mark.anyio
async def test_gas_sensor_service_start_stop(monkeypatch: pytest.MonkeyPatch):
    """Verify GasSensorService background lifecycle."""
    mock_settings = Settings(
        gas_sensor_enabled=True,
        gas_sensor_interval_s=0.05,
        gas_sensor_min=0.0,
        gas_sensor_max=100.0,
    )
    monkeypatch.setattr("backend.app.services.gas_sensor.get_settings", lambda: mock_settings)

    service = GasSensorService()
    service.start()
    assert service._task is not None
    assert not service._task.done()

    await asyncio.sleep(0.12)
    reading = service.get_latest_reading()
    assert "value" in reading
    assert "status" in reading

    await service.stop()
    assert service._task is None
