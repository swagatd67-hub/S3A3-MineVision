from typing import Any, Literal

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


class RobotCommandRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="Command name, e.g. MOVE, STOP, EMERGENCY_STOP, CAMERA_PAN")
    arguments: dict[str, Any] | None = Field(default=None, description="Command arguments dictionary")


class RobotCommandResponse(BaseModel):
    robot_id: str
    command: str
    status: Literal["accepted", "rejected"]
    controller_state: str
    timestamp: str
