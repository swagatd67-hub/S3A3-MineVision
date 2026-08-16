from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Mission, Telemetry
from backend.app.services.analytics import build_telemetry_analytics
from backend.app.services.cross_sensor import build_cross_sensor_events
from backend.app.services.graph_engine import build_distance_indexed_charts

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _mission_rows(mission_id: str, db: Session) -> tuple[Mission | None, list[Telemetry]]:
    mission = db.get(Mission, mission_id)

    rows = db.scalars(
        select(Telemetry)
        .where(Telemetry.mission_id == mission_id)
        .order_by(Telemetry.timestamp.asc())
    ).all()

    return mission, list(rows)


@router.get("/telemetry/{robot_id}")
def get_telemetry_analytics(
    robot_id: str,
    limit: int = Query(default=500, ge=10, le=5000),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(Telemetry)
        .where(Telemetry.robot_id == robot_id)
        .order_by(Telemetry.timestamp.desc())
        .limit(limit)
    ).all()

    rows = list(rows)
    rows.reverse()
    return build_telemetry_analytics(rows)


@router.get("/missions/{mission_id}")
def get_mission_analytics(mission_id: str, db: Session = Depends(get_db)) -> dict:
    mission, rows = _mission_rows(mission_id, db)

    if mission is None:
        return {"error": "mission_not_found", "mission_id": mission_id}

    analytics = build_telemetry_analytics(rows)
    analytics.update(
        {
            "mission_id": mission.mission_id,
            "robot_id": mission.robot_id,
            "mission_status": mission.status,
            "objective": mission.objective,
        }
    )
    return analytics


@router.get("/missions/{mission_id}/charts")
def get_mission_charts(
    mission_id: str,
    include_timeline: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    mission, rows = _mission_rows(mission_id, db)

    if mission is None:
        return {"error": "mission_not_found", "mission_id": mission_id}

    result = {
        "mission_id": mission.mission_id,
        "robot_id": mission.robot_id,
        "mission_status": mission.status,
        "objective": mission.objective,
        **build_distance_indexed_charts(rows),
    }

    if include_timeline:
        result["timeline"] = [
            {
                "distance_m": row.distance_m,
                "timestamp": row.timestamp,
                "state": row.state,
            }
            for row in rows
            if row.distance_m is not None
        ]

    return result


@router.get("/missions/{mission_id}/events")
def get_mission_events(
    mission_id: str,
    min_severity: str = Query(default="info"),
    db: Session = Depends(get_db),
) -> dict:
    mission, rows = _mission_rows(mission_id, db)

    if mission is None:
        return {"error": "mission_not_found", "mission_id": mission_id}

    events = build_cross_sensor_events(rows)

    severity_rank = {"info": 0, "warning": 1, "critical": 2}
    threshold = severity_rank.get(min_severity, 0)
    events = [
        event
        for event in events
        if severity_rank.get(event["severity"], 0) >= threshold
    ]

    return {
        "mission_id": mission.mission_id,
        "robot_id": mission.robot_id,
        "event_count": len(events),
        "events": events,
    }
