from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import InspectionObservationRow, Mission
from backend.app.schemas.mission import MissionCreate
from backend.app.services.mission.exceptions import (
    InvalidMissionLifecycleError,
    MissionNotFoundError,
    RobotMismatchError,
)
from backend.app.services.mission.orchestrator import orchestrator

router = APIRouter(prefix="/missions", tags=["missions"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def mission_to_dict(mission: Mission) -> dict:
    return {
        "mission_id": mission.mission_id,
        "robot_id": mission.robot_id,
        "objective": mission.objective,
        "status": mission.status,
        "created_at": mission.created_at,
        "started_at": mission.started_at,
        "completed_at": mission.completed_at,
        "notes": mission.notes,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_mission(
    request: MissionCreate,
    db: DatabaseSession,
) -> dict:
    try:
        mission = orchestrator.create_mission(
            db,
            robot_id=request.robot_id,
            objective=request.objective,
            notes=request.notes,
        )
        return mission_to_dict(mission)
    except RobotMismatchError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Robot not registered"
        ) from err


@router.get("")
def list_missions(db: DatabaseSession) -> list[dict]:
    missions = db.scalars(select(Mission).order_by(Mission.created_at.desc())).all()
    return [mission_to_dict(m) for m in missions]


@router.get("/{mission_id}")
def get_mission(mission_id: str, db: DatabaseSession) -> dict:
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        )
    return mission_to_dict(mission)


@router.post("/{mission_id}/start")
def start_mission(mission_id: str, db: DatabaseSession) -> dict:
    try:
        mission = orchestrator.start_mission(db, mission_id)
        return mission_to_dict(mission)
    except MissionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        ) from err
    except InvalidMissionLifecycleError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err


@router.post("/{mission_id}/pause")
def pause_mission(mission_id: str, db: DatabaseSession) -> dict:
    try:
        mission = orchestrator.pause_mission(db, mission_id)
        return mission_to_dict(mission)
    except MissionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        ) from err
    except InvalidMissionLifecycleError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err


@router.post("/{mission_id}/resume")
def resume_mission(mission_id: str, db: DatabaseSession) -> dict:
    try:
        mission = orchestrator.resume_mission(db, mission_id)
        return mission_to_dict(mission)
    except MissionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        ) from err
    except InvalidMissionLifecycleError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err


@router.post("/{mission_id}/complete")
def complete_mission(mission_id: str, db: DatabaseSession) -> dict:
    try:
        mission = orchestrator.complete_mission(db, mission_id)
        return mission_to_dict(mission)
    except MissionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        ) from err
    except InvalidMissionLifecycleError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err


@router.post("/{mission_id}/cancel")
def cancel_mission(mission_id: str, db: DatabaseSession) -> dict:
    try:
        mission = orchestrator.cancel_mission(db, mission_id)
        return mission_to_dict(mission)
    except MissionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        ) from err
    except InvalidMissionLifecycleError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err


@router.get("/{mission_id}/snapshot")
def get_mission_snapshot(mission_id: str, db: DatabaseSession) -> dict:
    try:
        snapshot = orchestrator.get_mission_snapshot(db, mission_id)
        return snapshot.to_dict()
    except MissionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        ) from err


@router.get("/{mission_id}/digital_twin")
def get_mission_digital_twin(mission_id: str, db: DatabaseSession) -> dict:
    try:
        snapshot = orchestrator.get_mission_snapshot(db, mission_id)
        return snapshot.digital_twin or {}
    except MissionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        ) from err


@router.get("/{mission_id}/reconstruction3d")
def get_mission_3d_reconstruction(mission_id: str, db: DatabaseSession) -> dict:
    from backend.app.services.reconstruction_3d import generate_3d_reconstruction
    try:
        reconstruction = generate_3d_reconstruction(db, mission_id)
        return reconstruction.model_dump(mode="json")
    except MissionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        ) from err



@router.get("/{mission_id}/observations")
def get_mission_observations(mission_id: str, db: DatabaseSession) -> dict:
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found"
        )

    rows = db.scalars(
        select(InspectionObservationRow)
        .where(InspectionObservationRow.mission_id == mission_id)
        .order_by(InspectionObservationRow.frame_index.asc())
    ).all()

    return {
        "mission_id": mission_id,
        "count": len(rows),
        "observations": [
            {
                "observation_id": row.observation_id,
                "frame_index": row.frame_index,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "distance_m": row.distance_m,
                "class_code": row.class_code,
                "confidence": row.confidence,
                "localization_quality": row.localization_quality,
                "model_name": row.model_name,
                "model_version": row.model_version,
                "box": row.box,
            }
            for row in rows
        ],
    }
