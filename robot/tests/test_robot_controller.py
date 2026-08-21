"""Focused unit tests for RobotController and Safety State Machine."""

from __future__ import annotations

from typing import Any

import pytest

from robot.control import (
    ControllerError,
    ControllerNotConnectedError,
    ControllerSafetyError,
    ControllerState,
    ControllerValidationError,
    RobotController,
)
from robot.transport.base import RobotTransport, TransportConnectionError
from robot.transport.simulator import SimulatorTransport


class RecordingFakeTransport(RobotTransport):
    """Fake transport to record all sent command payloads."""

    def __init__(self) -> None:
        self._connected = False
        self.sent_messages: list[dict[str, Any]] = []


    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def send(self, message: dict[str, Any] | str) -> None:
        if not self._connected:
            raise TransportConnectionError("Not connected")
        if isinstance(message, dict):
            self.sent_messages.append(message)


    def receive(
        self, timeout: float | None = None
    ) -> dict[str, Any] | str | None:
        return None


# 1. Initial state
def test_initial_state() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    assert ctrl.state == ControllerState.DISCONNECTED
    assert not ctrl.is_connected


# 2. Connect
def test_connect() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    assert ctrl.state == ControllerState.IDLE
    assert ctrl.is_connected
    assert sim.is_connected


# 3. Disconnect
def test_disconnect() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.disconnect()
    assert ctrl.state == ControllerState.DISCONNECTED
    assert not ctrl.is_connected
    assert not sim.is_connected


# 4. Move while disconnected
def test_move_while_disconnected() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    with pytest.raises(ControllerNotConnectedError, match="disconnected"):
        ctrl.move(0.5, 0.0)


# 5. Valid move
def test_valid_move() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.move(0.5, 0.1)
    assert ctrl.state == ControllerState.MOVING
    packet = ctrl.poll()
    assert isinstance(packet, dict)
    assert packet["state"] == "INSPECTING"


# 6. Invalid linear speed
def test_invalid_linear_speed() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim, max_linear_speed=1.0)
    ctrl.connect()
    with pytest.raises(ControllerValidationError, match="Linear speed"):
        ctrl.move(1.5, 0.0)


# 7. Invalid angular speed
def test_invalid_angular_speed() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim, max_angular_speed=2.0)
    ctrl.connect()
    with pytest.raises(ControllerValidationError, match="Angular speed"):
        ctrl.move(0.0, 2.5)


# 8. Stop
def test_stop() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.move(0.4, 0.0)
    ctrl.stop()
    assert ctrl.state == ControllerState.IDLE
    packet = ctrl.poll()
    assert isinstance(packet, dict)
    assert packet["state"] == "IDLE"


# 9. Repeated stop
def test_repeated_stop() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.stop()
    ctrl.stop()
    assert ctrl.state == ControllerState.IDLE


# 10. Emergency stop
def test_emergency_stop() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.emergency_stop()
    assert ctrl.state == ControllerState.EMERGENCY_STOP
    packet = ctrl.poll()
    assert isinstance(packet, dict)
    assert packet["state"] == "EMERGENCY_STOP"


# 11. Repeated emergency stop
def test_repeated_emergency_stop() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.emergency_stop()
    ctrl.emergency_stop()
    assert ctrl.state == ControllerState.EMERGENCY_STOP


# 12. Movement after emergency stop must fail
def test_movement_after_emergency_stop_must_fail() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.emergency_stop()
    with pytest.raises(ControllerSafetyError, match="EMERGENCY_STOP"):
        ctrl.move(0.5, 0.0)


# 13. Transport failure handling
def test_transport_failure_handling() -> None:
    class FailingTransport(RobotTransport):
        def connect(self) -> None:
            raise TransportConnectionError("Hardware failed")

        def disconnect(self) -> None:
            pass

        @property
        def is_connected(self) -> bool:
            return False

        def send(self, message: dict[str, Any] | str) -> None:
            raise TransportConnectionError("Write failed")

        def receive(
            self, timeout: float | None = None
        ) -> dict[str, Any] | str | None:
            return None

    fail_tr = FailingTransport()
    ctrl = RobotController(fail_tr)
    with pytest.raises(ControllerError, match="Failed to connect"):
        ctrl.connect()
    assert ctrl.state == ControllerState.FAULT


# 14. Camera pan
def test_camera_pan() -> None:
    rec = RecordingFakeTransport()
    ctrl = RobotController(rec)
    ctrl.connect()
    ctrl.camera_pan(45.0)
    assert len(rec.sent_messages) == 1
    assert rec.sent_messages[0] == {
        "name": "CAMERA_PAN",
        "arguments": {"angle_deg": 45.0},
    }


# 15. Cleaning commands
def test_cleaning_commands() -> None:
    rec = RecordingFakeTransport()
    ctrl = RobotController(rec)
    ctrl.connect()
    ctrl.clean_start("HIGH_PRESSURE")
    ctrl.clean_stop()
    assert rec.sent_messages == [
        {"name": "CLEAN_START", "arguments": {"mode": "HIGH_PRESSURE"}},
        {"name": "CLEAN_STOP"},
    ]


# 16. Sampling commands
def test_sampling_commands() -> None:
    rec = RecordingFakeTransport()
    ctrl = RobotController(rec)
    ctrl.connect()
    ctrl.sample_open()
    ctrl.sample_close()
    assert rec.sent_messages == [
        {"name": "SAMPLE_OPEN"},
        {"name": "SAMPLE_CLOSE"},
    ]


# 17. Inflate
def test_inflate() -> None:
    rec = RecordingFakeTransport()
    ctrl = RobotController(rec)
    ctrl.connect()
    ctrl.inflate(150.0)
    assert rec.sent_messages == [
        {"name": "INFLATE", "arguments": {"target_pressure_kpa": 150.0}}
    ]


# 18. Deflate
def test_deflate() -> None:
    rec = RecordingFakeTransport()
    ctrl = RobotController(rec)
    ctrl.connect()
    ctrl.deflate()
    assert rec.sent_messages == [{"name": "DEFLATE"}]


# 19. Hold pressure
def test_hold_pressure() -> None:
    rec = RecordingFakeTransport()
    ctrl = RobotController(rec)
    ctrl.connect()
    ctrl.hold_pressure(120.0)
    assert rec.sent_messages == [
        {"name": "HOLD_PRESSURE", "arguments": {"target_pressure_kpa": 120.0}}
    ]


# 20. Simulator state after MOVE
def test_simulator_state_after_move() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.move(0.3, 0.0)
    assert sim._current_state == "INSPECTING"


# 21. Simulator state after STOP
def test_simulator_state_after_stop() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.move(0.3, 0.0)
    ctrl.stop()
    assert sim._current_state == "IDLE"


# 22. Simulator state after EMERGENCY_STOP
def test_simulator_state_after_emergency_stop() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    ctrl.connect()
    ctrl.emergency_stop()
    assert sim._current_state == "EMERGENCY_STOP"


# 23. Dependency injection with a fake transport & no bypass
def test_dependency_injection_no_bypass() -> None:
    rec = RecordingFakeTransport()
    ctrl = RobotController(rec)
    ctrl.connect()
    ctrl.move(0.2, 0.1)
    ctrl.stop()
    ctrl.camera_pan(10.0)
    ctrl.emergency_stop()

    # All commands were captured through send()
    assert len(rec.sent_messages) == 4
    assert rec.sent_messages[0]["name"] == "MOVE"
    assert rec.sent_messages[1]["name"] == "STOP"
    assert rec.sent_messages[2]["name"] == "CAMERA_PAN"
    assert rec.sent_messages[3]["name"] == "EMERGENCY_STOP"



# 24. Poll connection & telemetry
def test_poll_connection() -> None:
    sim = SimulatorTransport()
    ctrl = RobotController(sim)
    assert ctrl.poll() is None  # Disconnected -> None
    ctrl.connect()
    telemetry = ctrl.poll()
    assert isinstance(telemetry, dict)
    assert "robot_id" in telemetry


# 25. All non-emergency commands rejected in FAULT and EMERGENCY_STOP
def test_all_non_emergency_commands_rejected_in_fault_and_estop() -> None:
    for state in (ControllerState.FAULT, ControllerState.EMERGENCY_STOP):
        rec = RecordingFakeTransport()
        ctrl = RobotController(rec)
        ctrl.connect()
        ctrl._state = state

        non_emergency_cmds = [
            lambda c=ctrl: c.move(0.1, 0.0),
            lambda c=ctrl: c.camera_pan(10.0),
            lambda c=ctrl: c.clean_start("MODE1"),
            lambda c=ctrl: c.clean_stop(),
            lambda c=ctrl: c.sample_open(),
            lambda c=ctrl: c.sample_close(),
            lambda c=ctrl: c.inflate(50.0),
            lambda c=ctrl: c.deflate(),
            lambda c=ctrl: c.hold_pressure(50.0),
        ]

        for cmd in non_emergency_cmds:
            with pytest.raises(ControllerSafetyError):
                cmd()


# 26. Recovery commands allowed in FAULT and EMERGENCY_STOP
def test_recovery_commands_allowed_in_fault_and_estop() -> None:
    for state in (ControllerState.FAULT, ControllerState.EMERGENCY_STOP):
        rec = RecordingFakeTransport()
        ctrl = RobotController(rec)
        ctrl.connect()
        ctrl._state = state

        # stop() and emergency_stop() must not raise ControllerSafetyError
        ctrl.stop()
        ctrl.emergency_stop()
