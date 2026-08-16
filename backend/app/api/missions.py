from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from backend.app.schemas.mission import MissionCreate, Mission

router = APIRouter(prefix="/missions", tags=["missions"])
_MISSIONS: dict[str, Mission] = {}

@router.post("", response_model=Mission)
def create_mission(request: MissionCreate):
    mission = Mission(mission_id=f"M-{uuid4().hex[:8].upper()}", robot_id=request.robot_id,
                      objective=request.objective, status="CREATED", created_at=datetime.now(timezone.utc))
    _MISSIONS[mission.mission_id] = mission
    return mission

@router.get("/{mission_id}", response_model=Mission)
def get_mission(mission_id: str):
    mission = _MISSIONS.get(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission
