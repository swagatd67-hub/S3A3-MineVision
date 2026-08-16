from fastapi import APIRouter, HTTPException
from backend.app.schemas.robot import RobotInfo, RobotRegistrationResponse

router = APIRouter(prefix="/robots", tags=["robots"])
_ROBOTS: dict[str, RobotInfo] = {}

@router.post("/register", response_model=RobotRegistrationResponse)
def register_robot(robot: RobotInfo):
    _ROBOTS[robot.robot_id] = robot
    return RobotRegistrationResponse(robot_id=robot.robot_id, status="registered", capabilities=robot.capabilities)

@router.get("/{robot_id}", response_model=RobotInfo)
def get_robot(robot_id: str):
    robot = _ROBOTS.get(robot_id)
    if robot is None:
        raise HTTPException(status_code=404, detail="Robot not registered")
    return robot
