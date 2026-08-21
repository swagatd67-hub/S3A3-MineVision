"""Unit tests for PipeVision Robot Transport layer."""

import pytest

from robot.transport import (
    EthernetTransport,
    InvalidMessageError,
    RobotTransport,
    SerialTransport,
    SimulatorTransport,
    TransportConnectionError,
    TransportNotConnectedError,
    validate_command_dict,
)


def test_robot_transport_abstract_interface() -> None:
    class DummyTransport(RobotTransport):
        def connect(self) -> None:
            pass

        def disconnect(self) -> None:
            pass

        @property
        def is_connected(self) -> bool:
            return True

        def send(self, message: dict | str) -> None:
            pass

        def receive(self, timeout: float | None = None) -> dict | str | None:
            return None

    dummy = DummyTransport()
    assert isinstance(dummy, RobotTransport)
    assert dummy.is_connected is True


def test_simulator_transport_lifecycle() -> None:
    sim = SimulatorTransport(robot_id="PV-SIM-TEST")
    assert not sim.is_connected

    sim.connect()
    assert sim.is_connected

    packet = sim.receive(timeout=0.1)
    assert packet is not None
    assert isinstance(packet, dict)
    assert packet["robot_id"] == "PV-SIM-TEST"
    assert "imu" in packet
    assert "pressure" in packet
    assert "water" in packet

    sim.disconnect()
    assert not sim.is_connected


def test_simulator_disconnected_behavior() -> None:
    sim = SimulatorTransport()
    assert not sim.is_connected

    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        sim.send({"name": "STOP"})

    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        sim.receive()

    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        sim.step()


def test_simulator_send_and_receive_commands() -> None:
    sim = SimulatorTransport()
    sim.connect()

    sim.send({"name": "MOVE", "arguments": {"linear": 0.4, "angular": 0.0}})
    packet = sim.receive(timeout=0.1)
    assert isinstance(packet, dict)
    assert packet["state"] == "INSPECTING"

    sim.send({"name": "STOP"})
    packet = sim.receive(timeout=0.1)
    assert isinstance(packet, dict)
    assert packet["state"] == "IDLE"

    sim.send({"name": "EMERGENCY_STOP"})
    packet = sim.receive(timeout=0.1)
    assert isinstance(packet, dict)
    assert packet["state"] == "EMERGENCY_STOP"

    sim.disconnect()


def test_invalid_command_validation() -> None:
    with pytest.raises(InvalidMessageError, match="Unknown command name"):
        validate_command_dict({"name": "FLY_TO_MARS"})

    with pytest.raises(InvalidMessageError, match="missing required argument"):
        validate_command_dict({"name": "MOVE", "arguments": {"linear": 0.5}})

    with pytest.raises(InvalidMessageError, match="expected float"):
        validate_command_dict(
            {"name": "MOVE", "arguments": {"linear": "fast", "angular": 0.0}}
        )

    with pytest.raises(InvalidMessageError, match="must be a dictionary"):
        validate_command_dict(12345)  # type: ignore[arg-type]


def test_simulator_invalid_message_handling() -> None:
    sim = SimulatorTransport()
    sim.connect()

    with pytest.raises(InvalidMessageError, match="Unknown command name"):
        sim.send({"name": "INVALID_CMD"})

    with pytest.raises(InvalidMessageError, match="Invalid JSON string"):
        sim.send("{not valid json")

    sim.disconnect()


def test_serial_transport_disconnected_behavior() -> None:
    serial_tr = SerialTransport(port="COM99")
    assert not serial_tr.is_connected

    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        serial_tr.send({"name": "STOP"})

    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        serial_tr.receive()


def test_serial_transport_connection_failure() -> None:
    serial_tr = SerialTransport(port="NON_EXISTENT_PORT_1234")
    with pytest.raises(TransportConnectionError):
        serial_tr.connect()


def test_ethernet_transport_disconnected_behavior() -> None:
    eth = EthernetTransport(host="127.0.0.1", port=9999)
    assert not eth.is_connected

    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        eth.send({"name": "STOP"})

    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        eth.receive()


def test_ethernet_transport_connection_failure() -> None:
    eth = EthernetTransport(host="192.0.2.1", port=9999, timeout=0.1)
    with pytest.raises(TransportConnectionError, match="Failed to connect"):
        eth.connect()
