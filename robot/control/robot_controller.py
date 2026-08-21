"""PipeVision Robot Controller with Safety State Machine."""

from __future__ import annotations

from enum import Enum
from typing import Any

from robot.transport.base import RobotTransport, TransportError


class ControllerState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    IDLE = "IDLE"
    MOVING = "MOVING"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    FAULT = "FAULT"


class ControllerError(Exception):
    """Base exception for robot controller errors."""


class ControllerNotConnectedError(ControllerError):
    """Raised when attempting an operation while robot controller is disconnected."""


class ControllerSafetyError(ControllerError):
    """Raised when an operation violates controller safety constraints."""


class ControllerValidationError(ControllerError):
    """Raised when input arguments violate configured speed limits or bounds."""


class RobotController:
    """Central safety controller mapping high-level commands to RobotTransport."""

    def __init__(
        self,
        transport: RobotTransport,
        max_linear_speed: float = 1.0,
        max_angular_speed: float = 2.0,
    ) -> None:
        self._transport = transport
        self.max_linear_speed = max_linear_speed
        self.max_angular_speed = max_angular_speed
        self._state: ControllerState = ControllerState.DISCONNECTED

    @property
    def transport(self) -> RobotTransport:
        return self._transport

    @property
    def state(self) -> ControllerState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return (
            self._state != ControllerState.DISCONNECTED
            and self._transport.is_connected
        )

    def connect(self) -> None:
        """Connect to transport and transition to IDLE state."""
        try:
            if not self._transport.is_connected:
                self._transport.connect()
            self._state = ControllerState.IDLE
        except TransportError as exc:
            self._state = ControllerState.FAULT
            raise ControllerError(
                f"Failed to connect transport: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Attempt to stop motion cleanly and disconnect transport."""
        if self.is_connected and self._state not in (
            ControllerState.EMERGENCY_STOP,
            ControllerState.FAULT,
        ):
            try:
                self._send_command("STOP")
            except Exception:  # noqa: BLE001, S110
                pass

        try:
            self._transport.disconnect()
        except Exception:  # noqa: BLE001, S110
            pass
        finally:
            self._state = ControllerState.DISCONNECTED

    def poll(self) -> dict[str, Any] | str | None:
        """Poll transport connection and receive pending telemetry/messages non-blockingly."""
        if self._state == ControllerState.DISCONNECTED:
            return None

        if not self._transport.is_connected:
            self._state = ControllerState.DISCONNECTED
            return None

        try:
            return self._transport.receive(timeout=0.0)
        except TransportError as exc:
            self._state = ControllerState.FAULT
            raise ControllerError(
                f"Transport error during poll: {exc}"
            ) from exc

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            self._state = ControllerState.DISCONNECTED
            raise ControllerNotConnectedError(
                "Cannot execute command: robot is disconnected."
            )

    def _ensure_command_allowed(self, operation_name: str) -> None:
        if self._state == ControllerState.EMERGENCY_STOP:
            raise ControllerSafetyError(
                f"{operation_name} rejected: robot is in EMERGENCY_STOP state."
            )
        if self._state == ControllerState.FAULT:
            raise ControllerSafetyError(
                f"{operation_name} rejected: robot is in FAULT state."
            )
        self._ensure_connected()

    def _send_command(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> None:
        cmd: dict[str, Any] = {"name": name}
        if arguments is not None:
            cmd["arguments"] = arguments

        try:
            self._transport.send(cmd)
        except TransportError as exc:
            self._state = ControllerState.FAULT
            raise ControllerError(
                f"Transport error while executing '{name}': {exc}"
            ) from exc

    def stop(self) -> None:
        """Stop robot motion idempotently."""
        if self._state == ControllerState.DISCONNECTED:
            return

        if self._state in (ControllerState.EMERGENCY_STOP, ControllerState.FAULT):
            if self._transport.is_connected:
                try:
                    self._send_command("STOP")
                except Exception:  # noqa: BLE001, S110
                    pass
            return

        self._ensure_connected()
        self._send_command("STOP")
        self._state = ControllerState.IDLE

    def emergency_stop(self) -> None:
        """Trigger emergency stop idempotently and transition to EMERGENCY_STOP state."""
        self._state = ControllerState.EMERGENCY_STOP
        if self._transport.is_connected:
            try:
                self._send_command("EMERGENCY_STOP")
            except Exception:  # noqa: BLE001, S110
                pass

    def move(self, linear: float, angular: float) -> None:
        """Send movement command with strict velocity limits checking."""
        self._ensure_command_allowed("Movement")

        if abs(linear) > self.max_linear_speed:
            raise ControllerValidationError(
                f"Linear speed {linear} exceeds maximum allowed speed of {self.max_linear_speed}."
            )

        if abs(angular) > self.max_angular_speed:
            raise ControllerValidationError(
                f"Angular speed {angular} exceeds maximum allowed speed of {self.max_angular_speed}."
            )

        self._send_command(
            "MOVE", {"linear": linear, "angular": angular}
        )
        self._state = (
            ControllerState.MOVING
            if (linear != 0.0 or angular != 0.0)
            else ControllerState.IDLE
        )

    def camera_pan(self, angle_deg: float) -> None:
        """Pan camera to specified angle in degrees."""
        self._ensure_command_allowed("Camera pan")
        self._send_command("CAMERA_PAN", {"angle_deg": angle_deg})

    def clean_start(self, mode: str) -> None:
        """Start pipe cleaning mechanism with specified mode string."""
        self._ensure_command_allowed("Clean start")
        self._send_command("CLEAN_START", {"mode": mode})

    def clean_stop(self) -> None:
        """Stop pipe cleaning mechanism."""
        self._ensure_command_allowed("Clean stop")
        self._send_command("CLEAN_STOP")

    def sample_open(self) -> None:
        """Open sample collection mechanism."""
        self._ensure_command_allowed("Sample open")
        self._send_command("SAMPLE_OPEN")

    def sample_close(self) -> None:
        """Close sample collection mechanism."""
        self._ensure_command_allowed("Sample close")
        self._send_command("SAMPLE_CLOSE")

    def inflate(self, target_pressure_kpa: float) -> None:
        """Inflate robot crawler element to target pressure in kPa."""
        self._ensure_command_allowed("Inflate")
        self._send_command(
            "INFLATE", {"target_pressure_kpa": target_pressure_kpa}
        )

    def deflate(self) -> None:
        """Deflate robot crawler element."""
        self._ensure_command_allowed("Deflate")
        self._send_command("DEFLATE")

    def hold_pressure(self, target_pressure_kpa: float) -> None:
        """Maintain target pressure in kPa."""
        self._ensure_command_allowed("Hold pressure")
        self._send_command(
            "HOLD_PRESSURE", {"target_pressure_kpa": target_pressure_kpa}
        )
