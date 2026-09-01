"""Optional Raspberry Pi to Pico UART link foundation.

This module deliberately contains no motor or TB6612FNG behavior. It only
provides a small, versioned JSON-lines envelope for future Pico firmware.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol


class PicoUartError(RuntimeError):
    """Base error for Pico UART communication."""


@dataclass(frozen=True)
class PicoUartConfig:
    """Explicit UART settings; no port is selected by this abstraction."""

    port: str
    baudrate: int = 115200
    timeout_s: float = 1.0

    def __post_init__(self) -> None:
        if not self.port.strip():
            raise ValueError("Pico UART port must be configured when enabled.")
        if self.baudrate <= 0:
            raise ValueError("Pico UART baudrate must be positive.")
        if self.timeout_s <= 0:
            raise ValueError("Pico UART timeout must be positive.")


@dataclass(frozen=True)
class PicoMessage:
    """Minimal future-safe envelope exchanged with Pico firmware.

    ``kind`` is intentionally limited to envelope categories, while
    ``payload`` is reserved for a separately versioned future firmware API.
    """

    kind: str
    payload: dict[str, Any]
    version: int = 1

    def encode(self) -> bytes:
        if self.version != 1:
            raise ValueError("Unsupported Pico message version.")
        if self.kind not in {"command", "telemetry", "heartbeat", "ack"}:
            raise ValueError(f"Unsupported Pico message kind '{self.kind}'.")
        if not isinstance(self.payload, dict):
            raise TypeError("Pico message payload must be an object.")
        return (json.dumps({"protocol": "pipevision-pico", "version": self.version,
                            "kind": self.kind, "payload": self.payload},
                           separators=(",", ":")) + "\n").encode("utf-8")

    @classmethod
    def decode(cls, raw: bytes | str) -> PicoMessage:
        try:
            data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise PicoUartError(f"Invalid Pico message JSON: {exc}") from exc
        if not isinstance(data, dict) or data.get("protocol") != "pipevision-pico":
            raise PicoUartError("Invalid Pico message protocol marker.")
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise PicoUartError("Pico message payload must be an object.")
        message = cls(kind=data.get("kind", ""), payload=payload, version=data.get("version", 0))
        message.encode()  # validate version and kind
        return message


class PicoUartLink(Protocol):
    """Mockable lifecycle and message interface for a future Pico link."""

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def send(self, message: PicoMessage) -> None: ...
    def receive(self) -> PicoMessage | None: ...


class FakePicoUart:
    """In-memory Pico link for tests; never opens a serial device."""

    def __init__(self) -> None:
        self.connected = False
        self.sent: list[PicoMessage] = []
        self.incoming: list[PicoMessage] = []

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def send(self, message: PicoMessage) -> None:
        if not self.connected:
            raise PicoUartError("Pico UART link is disconnected.")
        message.encode()
        self.sent.append(message)

    def receive(self) -> PicoMessage | None:
        if not self.connected:
            raise PicoUartError("Pico UART link is disconnected.")
        return self.incoming.pop(0) if self.incoming else None


class SerialPicoUart:
    """PySerial-backed link loaded only when explicitly configured."""

    def __init__(self, config: PicoUartConfig, serial_factory: Any | None = None) -> None:
        self.config = config
        self._serial_factory = serial_factory
        self._serial: Any | None = None

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and bool(self._serial.is_open)

    def connect(self) -> None:
        if self.is_connected:
            return
        factory = self._serial_factory
        if factory is None:
            try:
                import serial
            except ImportError as exc:  # pragma: no cover - environment-specific
                raise PicoUartError("pyserial is required for Pico UART mode.") from exc
            factory = serial.Serial
        try:
            self._serial = factory(self.config.port, self.config.baudrate, timeout=self.config.timeout_s)
        except OSError as exc:
            raise PicoUartError(f"Failed to open Pico UART '{self.config.port}': {exc}") from exc

    def disconnect(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def send(self, message: PicoMessage) -> None:
        if not self.is_connected:
            raise PicoUartError("Pico UART link is disconnected.")
        self._serial.write(message.encode())
        self._serial.flush()

    def receive(self) -> PicoMessage | None:
        if not self.is_connected:
            raise PicoUartError("Pico UART link is disconnected.")
        raw = self._serial.readline()
        return PicoMessage.decode(raw) if raw else None
