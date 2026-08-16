from datetime import datetime
from typing import Literal
from pydantic import BaseModel

MissionObjective = Literal["INSPECT", "INSPECT_AND_CLEAN", "INSPECT_SAMPLE"]

class MissionCreate(BaseModel):
    robot_id: str
    objective: MissionObjective = "INSPECT"

class Mission(BaseModel):
    mission_id: str
    robot_id: str
    objective: MissionObjective
    status: str
    created_at: datetime
