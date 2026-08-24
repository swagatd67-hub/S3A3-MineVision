from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.app.realtime import TelemetryBroadcaster


@pytest.mark.anyio
async def test_telemetry_broadcaster_fast_slow_dead_clients() -> None:
    broadcaster = TelemetryBroadcaster()

    # Fast client: sends instantly
    fast_ws = AsyncMock()
    fast_ws.send_json = AsyncMock(return_value=None)
    broadcaster._clients.add(fast_ws)

    # Slow client: hangs longer than 0.5s timeout
    async def slow_send(msg: Any) -> None:
        await asyncio.sleep(1.0)

    slow_ws = AsyncMock()
    slow_ws.send_json = AsyncMock(side_effect=slow_send)
    broadcaster._clients.add(slow_ws)

    # Dead client: raises exception on send
    dead_ws = AsyncMock()
    dead_ws.send_json = AsyncMock(side_effect=RuntimeError("Connection closed"))
    broadcaster._clients.add(dead_ws)

    msg = {"type": "telemetry", "speed": 1.5}
    await broadcaster.broadcast(msg)

    # Fast client received message
    fast_ws.send_json.assert_called_once_with(msg)

    # Slow and dead clients were pruned from broadcaster._clients
    assert fast_ws in broadcaster._clients
    assert slow_ws not in broadcaster._clients
    assert dead_ws not in broadcaster._clients
