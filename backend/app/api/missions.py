from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Mission, Robot
from backend.app.schemas.mission import MissionCreate

router = APIRouter(prefix="/missions", tags=["missions"])


def mission_to_dict(mission: Mission) -> dict:
    return {
        "mission_id": mission.mission_id,
        "robot_id": mission.robot_id,
        "objective": mission.objective,
        "status": mission.status,
        "created_at": mission.created_at,
    }


@router.post("", status_code=201)
def create_mission(
    request: MissionCreate,
    db: Session = Depends(get_db),
) -> dict:
    robot = db.get(Robot, request.robot_id)
    if robot is None:
        raise HTTPException(status_code=404, detail="Robot not registered")

    mission = Mission(
        mission_id=f"M-{uuid4().hex[:8].upper()}",
        robot_id=request.robot_id,
        objective=request.objective,
        status="CREATED",
        created_at=datetime.now(timezone.utc),
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission_to_dict(mission)


@router.post("/{mission_id}/start")
def start_mission(mission_id: str, db: Session = Depends(get_db)) -> dict:
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    mission.status = "RUNNING"
    db.commit()
    db.refresh(mission)
    return mission_to_dict(mission)


@router.post("/{mission_id}/complete")
def complete_mission(mission_id: str, db: Session = Depends(get_db)) -> dict:
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    mission.status = "COMPLETED"
    db.commit()
    db.refresh(mission)
    return mission_to_dict(mission)


@router.get("/{mission_id}")
def get_mission(mission_id: str, db: Session = Depends(get_db)) -> dict:
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission_to_dict(mission)
