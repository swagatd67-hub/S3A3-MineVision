from datetime import datetime, timezone
from fastapi import APIRouter
from backend.app.schemas.telemetry import TelemetryPacket

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
_TELEMETRY: list[TelemetryPacket] = []

@router.post("", response_model=TelemetryPacket)
def ingest_telemetry(packet: TelemetryPacket):
    if packet.timestamp is None:
        packet.timestamp = datetime.now(timezone.utc)
    _TELEMETRY.append(packet)
    return packet

@router.get("/{robot_id}", response_model=list[TelemetryPacket])
def get_robot_telemetry(robot_id: str):
    return [p for p in _TELEMETRY if p.robot_id == robot_id][-100:]
