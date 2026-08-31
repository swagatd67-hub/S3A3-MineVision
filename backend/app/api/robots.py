from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Robot
from backend.app.schemas.robot import (
    RobotCommandRequest,
    RobotCommandResponse,
    RobotInfo,
    RobotRegistrationResponse,
)
from backend.app.services.robot.manager import robot_manager
from robot.control.robot_controller import (
    ControllerNotConnectedError,
    ControllerSafetyError,
    ControllerValidationError,
)
from robot.transport.base import TransportError

router = APIRouter(prefix="/robots", tags=["robots"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=RobotRegistrationResponse)
def register_robot(robot: RobotInfo, db: DatabaseSession):
    row = db.get(Robot, robot.robot_id)
    if row is None:
        row = Robot(
            robot_id=robot.robot_id,
            name=robot.name,
            firmware_version=robot.firmware_version,
            capabilities=robot.capabilities,
        )
        db.add(row)
    else:
        row.name = robot.name
        row.firmware_version = robot.firmware_version
        row.capabilities = robot.capabilities
    db.commit()
    return RobotRegistrationResponse(
        robot_id=robot.robot_id, status="registered", capabilities=robot.capabilities
    )


@router.get("", response_model=list[RobotInfo])
def list_robots(db: DatabaseSession):
    rows = db.scalars(select(Robot).order_by(Robot.created_at.desc())).all()
    return [
        RobotInfo(
            robot_id=r.robot_id,
            name=r.name,
            firmware_version=r.firmware_version,
            capabilities=r.capabilities or [],
        )
        for r in rows
    ]


@router.get("/{robot_id}", response_model=RobotInfo)
def get_robot(robot_id: str, db: DatabaseSession):
    row = db.get(Robot, robot_id)
    if row is None:
        raise HTTPException(404, f"Robot '{robot_id}' not registered")
    return RobotInfo(
        robot_id=row.robot_id,
        name=row.name,
        firmware_version=row.firmware_version,
        capabilities=row.capabilities or [],
    )


@router.post("/{robot_id}/command", response_model=RobotCommandResponse)
def send_robot_command(
    robot_id: str,
    payload: RobotCommandRequest,
    mission_id: str | None = None,
):
    """Execute a typed command on the specified robot."""
    try:
        return robot_manager.execute_command(
            robot_id=robot_id,
            command_name=payload.name,
            arguments=payload.arguments,
            mission_id=mission_id,
        )
    except ControllerNotConnectedError as exc:
        raise HTTPException(status_code=409, detail=f"Robot disconnected: {exc}") from exc
    except ControllerSafetyError as exc:
        raise HTTPException(status_code=409, detail=f"Robot safety rejection: {exc}") from exc
    except ControllerValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid command arguments: {exc}") from exc
    except TransportError as exc:
        raise HTTPException(status_code=502, detail=f"Robot transport failure: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Command execution error: {exc}") from exc


@router.post("/{robot_id}/estop", response_model=RobotCommandResponse)
def emergency_stop_robot(
    robot_id: str,
    mission_id: str | None = None,
):
    """Trigger emergency stop idempotently on the specified robot."""
    try:
        return robot_manager.emergency_stop(robot_id=robot_id, mission_id=mission_id)
    except ControllerNotConnectedError as exc:
        raise HTTPException(status_code=409, detail=f"Robot disconnected: {exc}") from exc
    except TransportError as exc:
        raise HTTPException(status_code=502, detail=f"Robot transport failure: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"E-Stop execution error: {exc}") from exc
