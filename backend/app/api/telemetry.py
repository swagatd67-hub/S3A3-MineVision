from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Telemetry
from backend.app.realtime import telemetry_broadcaster
from backend.app.schemas.telemetry import TelemetryPacket
from backend.app.services.realtime_analytics import build_live_analytics_update

router = APIRouter(prefix="/telemetry", tags=["telemetry"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def to_packet(row: Telemetry) -> TelemetryPacket:
    return TelemetryPacket(
        robot_id=row.robot_id,
        mission_id=row.mission_id,
        timestamp=row.timestamp,
        battery_percent=row.battery_percent,
        distance_m=row.distance_m,
        body_diameter_mm=row.body_diameter_mm,
        state=row.state,
        imu=row.imu,
        pressure=row.pressure,
        water=row.water,
    )


@router.post("", response_model=TelemetryPacket)
async def ingest_telemetry(
    packet: TelemetryPacket,
    db: DatabaseSession,
) -> TelemetryPacket:
    timestamp = packet.timestamp or datetime.now(timezone.utc)

    row = Telemetry(
        robot_id=packet.robot_id,
        mission_id=packet.mission_id,
        timestamp=timestamp,
        battery_percent=packet.battery_percent,
        distance_m=packet.distance_m,
        body_diameter_mm=packet.body_diameter_mm,
        state=packet.state,
        imu=packet.imu.model_dump() if packet.imu else None,
        pressure=packet.pressure.model_dump() if packet.pressure else None,
        water=packet.water.model_dump() if packet.water else None,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    normalized = to_packet(row)

    # 1) Raw telemetry packet for clients that need the full sensor payload.
    await telemetry_broadcaster.broadcast(
        {
            "type": "telemetry",
            "data": normalized.model_dump(mode="json"),
        }
    )

    # 2) Mission-scoped analytics update for live charts/alerts.
    if row.mission_id:
        analytics_update = build_live_analytics_update(
            db,
            mission_id=row.mission_id,
            telemetry_row=row,
        )
        await telemetry_broadcaster.broadcast(analytics_update)

    return normalized


@router.get("/mission/{mission_id}", response_model=list[TelemetryPacket])
def get_mission_telemetry(
    mission_id: str,
    db: DatabaseSession,
) -> list[TelemetryPacket]:
    rows = db.scalars(
        select(Telemetry)
        .where(Telemetry.mission_id == mission_id)
        .order_by(Telemetry.timestamp.asc())
    ).all()

    return [to_packet(row) for row in rows]


@router.get("/{robot_id}", response_model=list[TelemetryPacket])
def get_robot_telemetry(
    robot_id: str,
    db: DatabaseSession,
) -> list[TelemetryPacket]:
    rows = db.scalars(
        select(Telemetry)
        .where(Telemetry.robot_id == robot_id)
        .order_by(Telemetry.timestamp.asc())
        .limit(100)
    ).all()

    return [to_packet(row) for row in rows]
