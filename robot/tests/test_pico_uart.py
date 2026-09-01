"""Tests for the optional Pico UART envelope and fake link."""

from __future__ import annotations

import pytest

from robot.transport.pico_uart import FakePicoUart, PicoMessage, PicoUartConfig


def test_pico_message_round_trip() -> None:
    message = PicoMessage("heartbeat", {"source": "rpi"})
    decoded = PicoMessage.decode(message.encode())
    assert decoded == message


def test_pico_message_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="Unsupported Pico message kind"):
        PicoMessage("motor_command", {}).encode()


def test_fake_pico_uart_is_mockable() -> None:
    link = FakePicoUart()
    link.connect()
    message = PicoMessage("telemetry", {"status": "ready"})
    link.send(message)
    link.incoming.append(message)
    assert link.receive() == message
    link.disconnect()


def test_pico_uart_config_requires_port() -> None:
    with pytest.raises(ValueError, match="port must be configured"):
        PicoUartConfig(port="")
