import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class TelemetryBroadcaster:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        if not self._clients:
            return

        clients = list(self._clients)
        dead: list[WebSocket] = []

        async def _send(ws: WebSocket) -> None:
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=0.5)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to send message to WebSocket client: %s", exc)
                dead.append(ws)

        await asyncio.gather(*[_send(ws) for ws in clients])

        for ws in dead:
            self.disconnect(ws)


telemetry_broadcaster = TelemetryBroadcaster()
