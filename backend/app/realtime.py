from fastapi import WebSocket


class TelemetryBroadcaster:
    def __init__(self):
        self._clients = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


telemetry_broadcaster = TelemetryBroadcaster()
