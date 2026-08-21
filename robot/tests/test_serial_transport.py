"""Focused unit tests for SerialTransport using mock serial objects."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from robot.transport import (
    InvalidMessageError,
    SerialTransport,
    TransportConnectionError,
    TransportNotConnectedError,
)


class FakeSerial:
    """Mock serial instance mimicking PySerial serial.Serial object."""

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 115200,
        timeout: float = 1.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self.written_bytes = b""
        self.read_queue: list[bytes] = []
        self.write_exception: Exception | None = None
        self.read_exception: Exception | None = None
        self.flush_called = False
        self.closed = False

    def write(self, data: bytes) -> int:
        if self.write_exception:
            raise self.write_exception
        self.written_bytes += data
        return len(data)

    def flush(self) -> None:
        self.flush_called = True

    def readline(self) -> bytes:
        if self.read_exception:
            raise self.read_exception
        if self.read_queue:
            return self.read_queue.pop(0)
        return b""

    def close(self) -> None:
        self.is_open = False
        self.closed = True


def make_connected_serial_transport(
    fake_serial: FakeSerial | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> tuple[SerialTransport, FakeSerial]:
    """Helper to instantiate and connect a SerialTransport with a FakeSerial mock."""
    fake = fake_serial or FakeSerial()

    class FakeSerialModule:
        SerialException = OSError

        @staticmethod
        def Serial(port: str, baudrate: int, timeout: float) -> FakeSerial:
            fake.port = port
            fake.baudrate = baudrate
            fake.timeout = timeout
            return fake

    if monkeypatch:
        monkeypatch.setitem(sys.modules, "serial", FakeSerialModule)  # type: ignore[arg-type]

    tr = SerialTransport(port="COM3", baudrate=115200, timeout=1.0)
    tr.connect()
    return tr, fake


def test_initial_disconnected_state() -> None:
    tr = SerialTransport(port="COM3")
    assert not tr.is_connected


def test_connect_success(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    assert tr.is_connected
    assert fake.is_open


def test_connect_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    tr = make_connected_serial_transport(monkeypatch=monkeypatch)[0]
    serial_obj_1 = tr._serial
    tr.connect()
    assert tr._serial is serial_obj_1
    assert tr.is_connected


def test_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    tr.disconnect()
    assert not tr.is_connected
    assert fake.closed
    assert tr._serial is None


def test_disconnect_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    tr = make_connected_serial_transport(monkeypatch=monkeypatch)[0]
    tr.disconnect()
    assert not tr.is_connected
    tr.disconnect()
    assert not tr.is_connected


def test_send_valid_dict_command(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    cmd = {"name": "MOVE", "arguments": {"linear": 0.5, "angular": 0.0}}
    tr.send(cmd)
    assert fake.flush_called
    written = fake.written_bytes.decode("utf-8")
    assert written.endswith("\n")
    data = json.loads(written)
    assert data["name"] == "MOVE"
    assert data["arguments"]["linear"] == 0.5


def test_send_valid_json_command_string(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    json_str = '{"name": "STOP"}'
    tr.send(json_str)
    written = fake.written_bytes.decode("utf-8")
    assert written == '{"name": "STOP"}\n'


def test_reject_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    tr = make_connected_serial_transport(monkeypatch=monkeypatch)[0]
    with pytest.raises(InvalidMessageError, match="Invalid JSON string"):
        tr.send("{broken_json: true")


def test_reject_unknown_command(monkeypatch: pytest.MonkeyPatch) -> None:
    tr = make_connected_serial_transport(monkeypatch=monkeypatch)[0]
    with pytest.raises(InvalidMessageError, match="Unknown command name"):
        tr.send({"name": "UNKNOWN_CMD"})


def test_reject_missing_required_command_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tr = make_connected_serial_transport(monkeypatch=monkeypatch)[0]
    with pytest.raises(InvalidMessageError, match="missing required argument"):
        tr.send({"name": "MOVE", "arguments": {"linear": 0.5}})


def test_reject_send_while_disconnected() -> None:
    tr = SerialTransport()
    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        tr.send({"name": "STOP"})


def test_receive_valid_json_telemetry_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    payload = {"robot_id": "PV-01", "battery_percent": 98.5}
    fake.read_queue.append(json.dumps(payload).encode("utf-8") + b"\n")

    res = tr.receive(timeout=0.5)
    assert isinstance(res, dict)
    assert res["robot_id"] == "PV-01"
    assert res["battery_percent"] == 98.5


def test_receive_non_json_line_str(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    fake.read_queue.append(b"RAW_ASCII_STATUS_OK\n")

    res = tr.receive(timeout=0.5)
    assert res == "RAW_ASCII_STATUS_OK"


def test_receive_empty_line_none(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    fake.read_queue.append(b"\n")

    res = tr.receive(timeout=0.5)
    assert res is None


def test_receive_timeout_none(monkeypatch: pytest.MonkeyPatch) -> None:
    tr = make_connected_serial_transport(monkeypatch=monkeypatch)[0]
    res = tr.receive(timeout=0.1)
    assert res is None


def test_receive_while_disconnected() -> None:
    tr = SerialTransport()
    with pytest.raises(TransportNotConnectedError, match="disconnected"):
        tr.receive()


def test_temporary_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    fake.read_queue.append(b"OK\n")
    assert fake.timeout == 1.0
    tr.receive(timeout=0.2)
    assert fake.timeout == 1.0


def test_timeout_restoration_when_readline_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    fake.read_queue.append(b"DATA\n")
    fake.timeout = 5.0
    tr.receive(timeout=0.5)
    assert fake.timeout == 5.0


def test_timeout_restoration_when_readline_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    fake.timeout = 5.0
    fake.read_exception = OSError("Read hardware fault")

    with pytest.raises(TransportConnectionError, match="Serial read error"):
        tr.receive(timeout=0.5)

    assert fake.timeout == 5.0


def test_serial_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    fake.write_exception = OSError("USB disconnected during write")

    with pytest.raises(TransportConnectionError, match="Serial write error"):
        tr.send({"name": "STOP"})


def test_serial_read_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    tr, fake = make_connected_serial_transport(monkeypatch=monkeypatch)
    fake.read_exception = OSError("Framing error")

    with pytest.raises(TransportConnectionError, match="Serial read error"):
        tr.receive()


def test_serial_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingSerialModule:
        SerialException = OSError

        @staticmethod
        def Serial(port: str, baudrate: int, timeout: float) -> Any:
            raise OSError("Port COM99 unavailable")

    monkeypatch.setitem(sys.modules, "serial", FailingSerialModule)  # type: ignore[arg-type]

    tr = SerialTransport(port="COM99")
    with pytest.raises(TransportConnectionError, match="Failed to open serial port"):
        tr.connect()
    assert not tr.is_connected
