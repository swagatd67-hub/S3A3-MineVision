from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models import Robot
from backend.app.schemas.robot import RobotInfo,RobotRegistrationResponse
router=APIRouter(prefix="/robots",tags=["robots"])
@router.post("/register",response_model=RobotRegistrationResponse)
def register_robot(robot:RobotInfo,db:Session=Depends(get_db)):
 row=db.get(Robot,robot.robot_id)
 if row is None:
  row=Robot(robot_id=robot.robot_id,name=robot.name,firmware_version=robot.firmware_version,capabilities=robot.capabilities); db.add(row)
 else:
  row.name=robot.name; row.firmware_version=robot.firmware_version; row.capabilities=robot.capabilities
 db.commit(); return RobotRegistrationResponse(robot_id=robot.robot_id,status="registered",capabilities=robot.capabilities)
@router.get("",response_model=list[RobotInfo])
def list_robots(db:Session=Depends(get_db)):
 rows=db.scalars(select(Robot).order_by(Robot.created_at.desc())).all()
 return [RobotInfo(robot_id=r.robot_id,name=r.name,firmware_version=r.firmware_version,capabilities=r.capabilities or []) for r in rows]
@router.get("/{robot_id}",response_model=RobotInfo)
def get_robot(robot_id:str,db:Session=Depends(get_db)):
 row=db.get(Robot,robot_id)
 if row is None: raise HTTPException(404,"Robot not registered")
 return RobotInfo(robot_id=row.robot_id,name=row.name,firmware_version=row.firmware_version,capabilities=row.capabilities or [])
