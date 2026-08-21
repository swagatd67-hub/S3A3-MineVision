"""Serial (UART/RS232/USB) physical transport implementation."""

from __future__ import annotations

import json
from typing import Any

from robot.transport.base import (
    InvalidMessageError,
    RobotTransport,
    TransportConnectionError,
    TransportNotConnectedError,
    load_command_protocol,
    validate_command_dict,
)


class SerialTransport(RobotTransport):
    """Wired serial transport for UART/RS-232/USB robot connections."""

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 115200,
        timeout: float = 1.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Any | None = None
        self._protocol = load_command_protocol()

    def connect(self) -> None:
        if self.is_connected:
            return

        try:
            import serial
        except ImportError as exc:
            raise TransportConnectionError(
                "PySerial package is not installed. "
                "Install it with 'pip install pyserial'."
            ) from exc

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
        except (OSError, serial.SerialException) as exc:
            self._serial = None
            raise TransportConnectionError(
                f"Failed to open serial port '{self.port}': {exc}"
            ) from exc

    def disconnect(self) -> None:
        serial_connection = self._serial

        if serial_connection is None:
            return

        try:
            serial_connection.close()
        except OSError:
            pass
        finally:
            self._serial = None

    @property
    def is_connected(self) -> bool:
        serial_connection = self._serial
        return serial_connection is not None and serial_connection.is_open

    def _require_connection(self) -> Any:
        serial_connection = self._serial

        if serial_connection is None or not serial_connection.is_open:
            raise TransportNotConnectedError(
                "Serial transport is disconnected."
            )

        return serial_connection

    def send(self, message: dict[str, Any] | str) -> None:
        serial_connection = self._require_connection()

        if isinstance(message, dict):
            msg_dict = message
            raw_text = json.dumps(message)
        elif isinstance(message, str):
            try:
                msg_dict = json.loads(message)
            except json.JSONDecodeError as exc:
                raise InvalidMessageError(
                    f"Invalid JSON string: {exc}"
                ) from exc

            if not isinstance(msg_dict, dict):
                raise InvalidMessageError(
                    "JSON command must decode to an object."
                )

            raw_text = message
        else:
            raise InvalidMessageError(
                "Message must be a dictionary or a valid JSON string."
            )

        validate_command_dict(msg_dict, self._protocol)

        try:
            payload = (raw_text.rstrip("\r\n") + "\n").encode("utf-8")
            serial_connection.write(payload)
            serial_connection.flush()
        except OSError as exc:
            raise TransportConnectionError(
                f"Serial write error on '{self.port}': {exc}"
            ) from exc

    def receive(
        self,
        timeout: float | None = None,
    ) -> dict[str, Any] | str | None:
        serial_connection = self._require_connection()

        original_timeout = serial_connection.timeout
        timeout_changed = timeout is not None

        if timeout_changed:
            serial_connection.timeout = timeout

        try:
            line = serial_connection.readline()

            if not line:
                return None

            decoded = line.decode("utf-8").strip()

            if not decoded:
                return None

            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                return decoded

        except OSError as exc:
            raise TransportConnectionError(
                f"Serial read error on '{self.port}': {exc}"
            ) from exc
        finally:
            if timeout_changed:
                serial_connection.timeout = original_timeout