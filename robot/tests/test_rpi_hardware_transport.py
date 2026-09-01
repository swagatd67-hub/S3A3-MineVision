"""Unit tests for RaspberryPiHardwareTransport and transport abstraction layer."""

from __future__ import annotations

import pytest

from backend.app.config import reset_settings
from backend.app.services.robot.manager import (
    RobotManager,
    create_transport_from_config,
)
from robot.gateway.adapter import RobotGatewayAdapter
from robot.transport.base import InvalidMessageError, TransportNotConnectedError
from robot.transport.raspberry_pi import RaspberryPiHardwareTransport
from robot.transport.servo import (
    GpioZeroServoDriver,
    ServoConfig,
    ServoError,
    ServoRigConfig,
)
from robot.transport.simulator import SimulatorTransport


def test_raspberry_pi_hardware_transport_lifecycle() -> None:
    transport = RaspberryPiHardwareTransport(host="192.168.1.100", port=5000, dry_run=True)
    assert not transport.is_connected

    # Attempt send before connect raises exception
    with pytest.raises(TransportNotConnectedError):
        transport.send({"name": "MOVE", "arguments": {"linear": 1.0, "angular": 0.0}})

    # Connect in dry-run mode
    transport.connect()
    assert transport.is_connected

    # Send valid movement command
    transport.send({"name": "MOVE", "arguments": {"linear": 0.5, "angular": 0.2}})
    assert len(transport.sent_messages) == 1
    assert transport.sent_messages[0]["name"] == "MOVE"
    assert transport.sent_messages[0]["arguments"] == {"linear": 0.5, "angular": 0.2}

    # Send invalid command raises validation error
    with pytest.raises(InvalidMessageError):
        transport.send({"name": "INVALID_COMMAND_XYZ"})

    # Disconnect
    transport.disconnect()
    assert not transport.is_connected


def test_robot_gateway_adapter_with_raspberry_pi_transport() -> None:
    transport = RaspberryPiHardwareTransport(dry_run=True)
    adapter = RobotGatewayAdapter(transport=transport, robot_id="CRAWLER-RPI-01")

    adapter.connect()
    assert adapter.is_connected
    assert adapter.connection_state.value in ("CONNECTED", "STREAMING")

    # Issue drive command through RobotGatewayAdapter -> RobotController -> RaspberryPiHardwareTransport
    adapter.move(0.4, -0.1)
    assert len(transport.sent_messages) == 1
    assert transport.sent_messages[0]["name"] == "MOVE"
    assert transport.sent_messages[0]["arguments"] == {"linear": 0.4, "angular": -0.1}

    # Emergency stop
    adapter.emergency_stop()
    assert len(transport.sent_messages) == 2
    assert transport.sent_messages[1]["name"] == "EMERGENCY_STOP"

    adapter.disconnect()
    assert not adapter.is_connected


def test_robot_manager_transport_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = RobotManager()

    # 1. Default configuration returns SimulatorTransport
    reset_settings()
    monkeypatch.delenv("ROBOT_TRANSPORT_TYPE", raising=False)
    sim_adapter = manager.get_adapter(robot_id="ROBOT-SIM-TEST")
    assert isinstance(sim_adapter.transport, SimulatorTransport)

    # 2. Dynamic injection via transport_type="rpi"
    rpi_adapter = manager.get_adapter(robot_id="ROBOT-RPI-TEST", transport_type="rpi")
    assert isinstance(rpi_adapter.transport, RaspberryPiHardwareTransport)

    # 3. Environment configuration ROBOT_TRANSPORT_TYPE="rpi"
    monkeypatch.setenv("ROBOT_TRANSPORT_TYPE", "rpi")
    reset_settings()
    env_rpi_transport = create_transport_from_config(robot_id="ROBOT-ENV-TEST")
    assert isinstance(env_rpi_transport, RaspberryPiHardwareTransport)


def test_live_gpio_driver_rejects_incomplete_calibration_before_gpio_import() -> None:
    channels = {
        name: ServoConfig(name=name, gpio_pin=index)
        for index, name in enumerate(
            ("locomotion_1", "locomotion_2", "locomotion_3", "locomotion_4", "camera_pan", "camera_tilt")
        )
    }
    with pytest.raises(ServoError, match="requires configured neutral_deg"):
        GpioZeroServoDriver(ServoRigConfig(channels=channels))
