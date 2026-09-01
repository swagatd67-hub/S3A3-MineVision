"""Tests for the HAL transport factory (robot.transport.factory).

All tests run without physical hardware – either using the SimulatorTransport
or the RaspberryPiHardwareTransport in dry-run mode.
"""

from __future__ import annotations

import pytest

from backend.app.config import reset_settings
from backend.app.services.robot.manager import (
    RobotManager,
    create_transport_from_config,
)
from robot.gateway.adapter import RobotGatewayAdapter
from robot.transport.base import (
    InvalidMessageError,
    TransportNotConnectedError,
)
from robot.transport.ethernet import EthernetTransport
from robot.transport.factory import (
    SUPPORTED_TRANSPORT_TYPES,
    TransportFactoryError,
    create_transport,
)
from robot.transport.raspberry_pi import RaspberryPiHardwareTransport
from robot.transport.serial import SerialTransport
from robot.transport.simulator import SimulatorTransport

# ─────────────────────────────────────────────────────────────────────────────
# 1. Factory – transport type resolution
# ─────────────────────────────────────────────────────────────────────────────


class TestCreateTransportTypeResolution:
    """Verify each transport type alias resolves to the correct class."""

    def test_simulator_default(self) -> None:
        t = create_transport(robot_id="R01", transport_type="simulator")
        assert isinstance(t, SimulatorTransport)

    def test_simulator_alias_sim(self) -> None:
        t = create_transport(robot_id="R01", transport_type="sim")
        assert isinstance(t, SimulatorTransport)

    def test_rpi_alias_rpi(self) -> None:
        t = create_transport(robot_id="R01", transport_type="rpi", dry_run=True)
        assert isinstance(t, RaspberryPiHardwareTransport)

    def test_rpi_alias_raspberry_pi(self) -> None:
        t = create_transport(robot_id="R01", transport_type="raspberry_pi", dry_run=True)
        assert isinstance(t, RaspberryPiHardwareTransport)

    def test_rpi_alias_raspberrypi(self) -> None:
        t = create_transport(robot_id="R01", transport_type="raspberrypi", dry_run=True)
        assert isinstance(t, RaspberryPiHardwareTransport)

    def test_ethernet_alias_ethernet(self) -> None:
        t = create_transport(robot_id="R01", transport_type="ethernet")
        assert isinstance(t, EthernetTransport)
        assert t.protocol == "tcp"

    def test_ethernet_alias_tcp(self) -> None:
        t = create_transport(robot_id="R01", transport_type="tcp")
        assert isinstance(t, EthernetTransport)
        assert t.protocol == "tcp"

    def test_ethernet_alias_udp(self) -> None:
        t = create_transport(robot_id="R01", transport_type="udp")
        assert isinstance(t, EthernetTransport)
        assert t.protocol == "udp"

    def test_serial(self) -> None:
        t = create_transport(robot_id="R01", transport_type="serial")
        assert isinstance(t, SerialTransport)

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(TransportFactoryError, match="Unknown transport type"):
            create_transport(robot_id="R01", transport_type="LASER_BEAM")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Factory – parameter injection
# ─────────────────────────────────────────────────────────────────────────────


class TestCreateTransportParameterInjection:
    """Verify that caller-supplied parameters override defaults."""

    def test_simulator_mission_id_propagated(self) -> None:
        t = create_transport(
            robot_id="BOT-SIM-42",
            mission_id="MISSION-007",
            transport_type="simulator",
        )
        assert isinstance(t, SimulatorTransport)
        assert t.mission_id == "MISSION-007"
        assert t.robot_id == "BOT-SIM-42"

    def test_simulator_default_mission_id_fallback(self) -> None:
        t = create_transport(robot_id="BOT-SIM-99", transport_type="simulator")
        assert isinstance(t, SimulatorTransport)
        assert t.mission_id == "MISSION-ACTIVE"

    def test_rpi_host_port_override(self) -> None:
        t = create_transport(
            robot_id="R01",
            transport_type="rpi",
            host="10.0.0.42",
            port=9999,
            dry_run=True,
        )
        assert isinstance(t, RaspberryPiHardwareTransport)
        assert t.host == "10.0.0.42"
        assert t.port == 9999

    def test_rpi_dry_run_kwarg_true(self) -> None:
        t = create_transport(robot_id="R01", transport_type="rpi", dry_run=True)
        assert isinstance(t, RaspberryPiHardwareTransport)
        assert t.dry_run is True

    def test_serial_port_baudrate_override(self) -> None:
        t = create_transport(
            robot_id="R01",
            transport_type="serial",
            serial_port="COM5",
            baudrate=9600,
        )
        assert isinstance(t, SerialTransport)
        assert t.port == "COM5"
        assert t.baudrate == 9600

    def test_supported_transport_types_complete(self) -> None:
        expected = {"simulator", "sim", "rpi", "raspberry_pi", "raspberrypi",
                    "ethernet", "tcp", "udp", "serial"}
        assert expected.issubset(SUPPORTED_TRANSPORT_TYPES)


# ─────────────────────────────────────────────────────────────────────────────
# 3. RaspberryPiHardwareTransport – dry-run lifecycle
# ─────────────────────────────────────────────────────────────────────────────


class TestRpiTransportDryRunLifecycle:
    """Full lifecycle tests for RPi transport without physical hardware."""

    def test_not_connected_before_connect(self) -> None:
        t = RaspberryPiHardwareTransport(dry_run=True)
        assert not t.is_connected

    def test_send_before_connect_raises(self) -> None:
        t = RaspberryPiHardwareTransport(dry_run=True)
        with pytest.raises(TransportNotConnectedError):
            t.send({"name": "STOP"})

    def test_connect_sets_connected(self) -> None:
        t = RaspberryPiHardwareTransport(dry_run=True)
        t.connect()
        assert t.is_connected

    def test_connect_idempotent(self) -> None:
        t = RaspberryPiHardwareTransport(dry_run=True)
        t.connect()
        t.connect()  # second call should be a no-op
        assert t.is_connected

    def test_disconnect_clears_connected(self) -> None:
        t = RaspberryPiHardwareTransport(dry_run=True)
        t.connect()
        t.disconnect()
        assert not t.is_connected

    def test_reconnect_after_disconnect(self) -> None:
        t = RaspberryPiHardwareTransport(dry_run=True)
        t.connect()
        t.disconnect()
        t.connect()
        assert t.is_connected

    def test_dry_run_receive_returns_none(self) -> None:
        t = RaspberryPiHardwareTransport(dry_run=True)
        t.connect()
        result = t.receive(timeout=0.0)
        assert result is None

    def test_receive_before_connect_raises(self) -> None:
        t = RaspberryPiHardwareTransport(dry_run=True)
        with pytest.raises(TransportNotConnectedError):
            t.receive()


# ─────────────────────────────────────────────────────────────────────────────
# 4. RaspberryPiHardwareTransport – command round-trip (dry-run)
# ─────────────────────────────────────────────────────────────────────────────


class TestRpiTransportCommandRoundTrip:
    """Verify all protocol commands are serialised, validated, and recorded."""

    @pytest.fixture()
    def transport(self) -> RaspberryPiHardwareTransport:
        t = RaspberryPiHardwareTransport(dry_run=True)
        t.connect()
        return t

    def test_send_move_recorded(self, transport: RaspberryPiHardwareTransport) -> None:
        transport.send({"name": "MOVE", "arguments": {"linear": 0.3, "angular": -0.1}})
        assert len(transport.sent_messages) == 1
        msg = transport.sent_messages[0]
        assert msg["name"] == "MOVE"
        assert msg["arguments"]["linear"] == 0.3

    def test_send_stop_recorded(self, transport: RaspberryPiHardwareTransport) -> None:
        transport.send({"name": "STOP"})
        assert transport.sent_messages[-1]["name"] == "STOP"

    def test_send_emergency_stop_recorded(self, transport: RaspberryPiHardwareTransport) -> None:
        transport.send({"name": "EMERGENCY_STOP"})
        assert transport.sent_messages[-1]["name"] == "EMERGENCY_STOP"

    def test_send_camera_pan_recorded(self, transport: RaspberryPiHardwareTransport) -> None:
        transport.send({"name": "CAMERA_PAN", "arguments": {"angle_deg": 45.0}})
        assert transport.sent_messages[-1]["arguments"]["angle_deg"] == 45.0

    def test_send_inflate_recorded(self, transport: RaspberryPiHardwareTransport) -> None:
        transport.send({"name": "INFLATE", "arguments": {"target_pressure_kpa": 150.0}})
        assert transport.sent_messages[-1]["name"] == "INFLATE"

    def test_send_invalid_command_raises(self, transport: RaspberryPiHardwareTransport) -> None:
        with pytest.raises(InvalidMessageError):
            transport.send({"name": "SELF_DESTRUCT"})

    def test_send_json_string_accepted(self, transport: RaspberryPiHardwareTransport) -> None:
        import json
        transport.send(json.dumps({"name": "STOP"}))
        assert transport.sent_messages[-1]["name"] == "STOP"

    def test_send_invalid_json_raises(self, transport: RaspberryPiHardwareTransport) -> None:
        with pytest.raises(InvalidMessageError):
            transport.send("not valid json }{")

    def test_sent_messages_isolated(self, transport: RaspberryPiHardwareTransport) -> None:
        """sent_messages returns a copy – mutations don't affect internal state."""
        transport.send({"name": "STOP"})
        snapshot = transport.sent_messages
        snapshot.clear()
        assert len(transport.sent_messages) == 1

    def test_multiple_commands_ordered(self, transport: RaspberryPiHardwareTransport) -> None:
        transport.send({"name": "MOVE", "arguments": {"linear": 0.1, "angular": 0.0}})
        transport.send({"name": "CAMERA_PAN", "arguments": {"angle_deg": 30.0}})
        transport.send({"name": "STOP"})
        names = [m["name"] for m in transport.sent_messages]
        assert names == ["MOVE", "CAMERA_PAN", "STOP"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Gateway adapter – RPi in dry-run mode
# ─────────────────────────────────────────────────────────────────────────────


class TestGatewayAdapterWithRpiTransport:
    """Integration tests: RobotGatewayAdapter + RaspberryPiHardwareTransport (dry-run)."""

    @pytest.fixture()
    def adapter(self) -> RobotGatewayAdapter:
        t = RaspberryPiHardwareTransport(dry_run=True)
        a = RobotGatewayAdapter(transport=t, robot_id="RPI-GW-01")
        a.connect()
        return a

    def test_adapter_connected(self, adapter: RobotGatewayAdapter) -> None:
        assert adapter.is_connected

    def test_transport_type_exposed_in_health(self, adapter: RobotGatewayAdapter) -> None:
        health = adapter.get_health()
        assert health.transport_type == "RaspberryPiHardwareTransport"

    def test_move_command_flow(self, adapter: RobotGatewayAdapter) -> None:
        adapter.move(0.5, 0.0)
        t = adapter.transport
        assert isinstance(t, RaspberryPiHardwareTransport)
        assert t.sent_messages[-1]["name"] == "MOVE"
        assert t.sent_messages[-1]["arguments"]["linear"] == 0.5

    def test_emergency_stop_flow(self, adapter: RobotGatewayAdapter) -> None:
        adapter.move(0.2, 0.0)
        adapter.emergency_stop()
        t = adapter.transport
        assert isinstance(t, RaspberryPiHardwareTransport)
        assert t.sent_messages[-1]["name"] == "EMERGENCY_STOP"

    def test_full_command_set(self, adapter: RobotGatewayAdapter) -> None:
        from robot.control.robot_controller import (
            ControllerSafetyError,
            ControllerState,
        )

        adapter.move(0.1, 0.0)
        assert adapter.controller.state == ControllerState.MOVING
        adapter.camera_pan(90.0)
        adapter.clean_start("JETTING")
        adapter.clean_stop()
        adapter.inflate(150.0)
        adapter.hold_pressure(150.0)
        adapter.deflate()
        adapter.sample_open()
        adapter.sample_close()
        adapter.stop()
        assert adapter.controller.state == ControllerState.IDLE

        adapter.emergency_stop()
        assert adapter.controller.state == ControllerState.EMERGENCY_STOP
        # Further movement must be blocked
        with pytest.raises(ControllerSafetyError):
            adapter.move(0.1, 0.0)

    def test_disconnect_clears_connection(self, adapter: RobotGatewayAdapter) -> None:
        adapter.disconnect()
        assert not adapter.is_connected


# ─────────────────────────────────────────────────────────────────────────────
# 6. RobotManager – transport selection via DI and config
# ─────────────────────────────────────────────────────────────────────────────


class TestRobotManagerTransportSelection:
    """End-to-end transport selection through RobotManager."""

    def test_default_is_simulator(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reset_settings()
        monkeypatch.delenv("ROBOT_TRANSPORT_TYPE", raising=False)
        manager = RobotManager()
        adapter = manager.get_adapter("BOT-DEFAULT")
        assert isinstance(adapter.transport, SimulatorTransport)
        manager.disconnect_all()

    def test_explicit_rpi_via_transport_type_arg(self) -> None:
        manager = RobotManager()
        adapter = manager.get_adapter("BOT-RPI-INJ", transport_type="rpi")
        assert isinstance(adapter.transport, RaspberryPiHardwareTransport)
        assert adapter.transport.dry_run is True
        manager.disconnect_all()

    def test_explicit_direct_transport_injection(self) -> None:
        """Direct transport object injection takes highest priority."""
        sim = SimulatorTransport(robot_id="BOT-INJECT-01")
        manager = RobotManager()
        adapter = manager.get_adapter("BOT-INJECT-01", transport=sim)
        assert adapter.transport is sim
        manager.disconnect_all()

    def test_env_rpi_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROBOT_TRANSPORT_TYPE", "rpi")
        reset_settings()
        t = create_transport_from_config(robot_id="BOT-ENV-RPI")
        assert isinstance(t, RaspberryPiHardwareTransport)

    def test_env_simulator_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROBOT_TRANSPORT_TYPE", "simulator")
        reset_settings()
        t = create_transport_from_config(robot_id="BOT-ENV-SIM")
        assert isinstance(t, SimulatorTransport)

    def test_env_serial_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROBOT_TRANSPORT_TYPE", "serial")
        monkeypatch.setenv("ROBOT_SERIAL_PORT", "/dev/ttyUSB1")
        monkeypatch.setenv("ROBOT_BAUDRATE", "9600")
        reset_settings()
        t = create_transport_from_config(robot_id="BOT-ENV-SERIAL")
        assert isinstance(t, SerialTransport)
        assert t.port == "/dev/ttyUSB1"
        assert t.baudrate == 9600

    def test_env_dry_run_false_propagated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ROBOT_DRY_RUN=false must be propagated to the RPi transport."""
        monkeypatch.setenv("ROBOT_TRANSPORT_TYPE", "rpi")
        monkeypatch.setenv("ROBOT_DRY_RUN", "false")
        reset_settings()
        # We DON'T call connect() – just verify the attribute is set
        t = create_transport_from_config(robot_id="BOT-LIVE-RPI")
        assert isinstance(t, RaspberryPiHardwareTransport)
        assert t.dry_run is False

    def test_env_dry_run_true_propagated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROBOT_TRANSPORT_TYPE", "rpi")
        monkeypatch.setenv("ROBOT_DRY_RUN", "true")
        reset_settings()
        t = create_transport_from_config(robot_id="BOT-DRYRUN-RPI")
        assert isinstance(t, RaspberryPiHardwareTransport)
        assert t.dry_run is True

    def test_manager_reuses_connected_adapter(self) -> None:
        """Calling get_adapter twice with the same robot_id returns same adapter."""
        manager = RobotManager()
        a1 = manager.get_adapter("BOT-REUSE-01")
        a2 = manager.get_adapter("BOT-REUSE-01")
        assert a1 is a2
        manager.disconnect_all()

    def test_manager_disconnect_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reset_settings()
        monkeypatch.delenv("ROBOT_TRANSPORT_TYPE", raising=False)
        manager = RobotManager()
        manager.get_adapter("BOT-DC-01")
        manager.get_adapter("BOT-DC-02")
        manager.disconnect_all()
        # After disconnect, next call recreates adapters
        a_new = manager.get_adapter("BOT-DC-01")
        assert isinstance(a_new.transport, SimulatorTransport)
        manager.disconnect_all()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Factory – fallback when no settings available (standalone robot package)
# ─────────────────────────────────────────────────────────────────────────────


class TestFactoryStandaloneWithoutBackend:
    """The factory must work without the backend settings module."""

    def test_explicit_type_bypasses_settings(self) -> None:
        """When transport_type is explicit, no settings are needed."""
        t = create_transport(robot_id="STANDALONE", transport_type="simulator")
        assert isinstance(t, SimulatorTransport)

    def test_rpi_explicit_dry_run(self) -> None:
        t = create_transport(
            robot_id="STANDALONE-RPI",
            transport_type="rpi",
            dry_run=True,
            host="192.168.99.1",
            port=7777,
        )
        assert isinstance(t, RaspberryPiHardwareTransport)
        assert t.host == "192.168.99.1"
        assert t.port == 7777
