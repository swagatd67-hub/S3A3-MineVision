"""PipeVision Robot Gateway / Hardware Adapter Package."""

from robot.gateway.adapter import RobotGatewayAdapter
from robot.gateway.exceptions import (
    RobotGatewayConnectionError,
    RobotGatewayError,
    RobotGatewayStateError,
    RobotGatewayTimeoutError,
    RobotGatewayValidationError,
)
from robot.gateway.models import (
    GatewayConnectionState,
    GatewayFailureReason,
    GatewayHealth,
    HardwareFramePacket,
)

__all__ = [
    "GatewayConnectionState",
    "GatewayFailureReason",
    "GatewayHealth",
    "HardwareFramePacket",
    "RobotGatewayAdapter",
    "RobotGatewayConnectionError",
    "RobotGatewayError",
    "RobotGatewayStateError",
    "RobotGatewayTimeoutError",
    "RobotGatewayValidationError",
]
