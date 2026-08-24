"""PipeVision Robot Gateway / Hardware Adapter Package."""

from robot.gateway.adapter import RobotGatewayAdapter
from robot.gateway.exceptions import (
    RobotGatewayConnectionError,
    RobotGatewayError,
    RobotGatewayStateError,
    RobotGatewayTimeoutError,
    RobotGatewayValidationError,
)
from robot.gateway.hardware_config import (
    HardwareInterfaceConfig,
    create_hardware_config,
    validate_hardware_config,
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
    "HardwareInterfaceConfig",
    "RobotGatewayAdapter",
    "RobotGatewayConnectionError",
    "RobotGatewayError",
    "RobotGatewayStateError",
    "RobotGatewayTimeoutError",
    "RobotGatewayValidationError",
    "create_hardware_config",
    "validate_hardware_config",
]
