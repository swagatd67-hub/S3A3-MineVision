"""Ethernet (TCP/UDP socket) physical transport implementation."""

import json
import select
import socket
from typing import Any

from robot.transport.base import (
    InvalidMessageError,
    RobotTransport,
    TransportConnectionError,
    TransportNotConnectedError,
    load_command_protocol,
    validate_command_dict,
)


class EthernetTransport(RobotTransport):
    """Wired Ethernet transport for physical robot connection over TCP/IP or UDP."""

    def __init__(
        self,
        host: str = "192.168.1.100",
        port: int = 5000,
        protocol: str = "tcp",
        timeout: float = 1.0,
    ) -> None:
        self.host = host
        self.port = port
        self.protocol = protocol.lower()
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._protocol_schema = load_command_protocol()

    def connect(self) -> None:
        if self.protocol not in ("tcp", "udp"):
            raise TransportConnectionError(
                f"Unsupported ethernet protocol '{self.protocol}'. Expected 'tcp' or 'udp'."
            )

        sock: socket.socket | None = None
        try:
            sock_type = (
                socket.SOCK_STREAM if self.protocol == "tcp" else socket.SOCK_DGRAM
            )
            sock = socket.socket(socket.AF_INET, sock_type)
            sock.settimeout(self.timeout)

            if self.protocol == "tcp":
                sock.connect((self.host, self.port))

            self._socket = sock
        except Exception as err:
            if sock is not None:
                sock.close()
            raise TransportConnectionError(
                f"Failed to connect ethernet transport ({self.protocol.upper()} {self.host}:{self.port}): {err}"
            ) from err

    def disconnect(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            finally:
                self._socket = None

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    def send(self, message: dict[str, Any] | str) -> None:
        if not self.is_connected or self._socket is None:
            raise TransportNotConnectedError(
                "Cannot send message: ethernet transport is disconnected."
            )

        if isinstance(message, str):
            try:
                msg_dict = json.loads(message)
            except json.JSONDecodeError as err:
                raise InvalidMessageError(f"Invalid JSON string: {err}") from err
            raw_text = message
        elif isinstance(message, dict):
            msg_dict = message
            raw_text = json.dumps(message)
        else:
            raise InvalidMessageError(
                "Message must be a dictionary or a valid JSON string."
            )

        validate_command_dict(msg_dict, self._protocol_schema)

        try:
            payload = (raw_text.strip() + "\n").encode("utf-8")
            if self.protocol == "tcp":
                self._socket.sendall(payload)
            else:
                self._socket.sendto(payload, (self.host, self.port))
        except OSError as err:
            raise TransportConnectionError(f"Ethernet send error: {err}") from err

    def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None:
        if not self.is_connected or self._socket is None:
            raise TransportNotConnectedError(
                "Cannot receive message: ethernet transport is disconnected."
            )

        read_timeout = timeout if timeout is not None else self.timeout

        try:
            ready, _, _ = select.select([self._socket], [], [], read_timeout)
            if not ready:
                return None

            if self.protocol == "tcp":
                data = self._socket.recv(4096)
            else:
                data, _ = self._socket.recvfrom(4096)

            if not data:
                return None

            decoded = data.decode("utf-8").strip()
            if not decoded:
                return None

            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                return decoded
        except OSError as err:
            raise TransportConnectionError(f"Ethernet receive error: {err}") from err
