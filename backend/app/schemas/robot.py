from typing import Literal

from pydantic import BaseModel, Field

RobotCapability = Literal[
    "camera",
    "imu",
    "encoder",
    "water_quality",
    "pressure",
    "cleaning",
    "sampling",
    "adaptive_morphology",
    "depth_camera",
]


class RobotInfo(BaseModel):
    robot_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    firmware_version: str = "dev"
    capabilities: list[RobotCapability] = Field(default_factory=list)


class RobotRegistrationResponse(BaseModel):
    robot_id: str
    status: Literal["registered"]
    capabilities: list[RobotCapability]
