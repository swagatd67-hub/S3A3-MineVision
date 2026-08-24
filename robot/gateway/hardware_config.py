"""Hardware interface configuration and validation specifications for Phase 14."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from robot.gateway.exceptions import RobotGatewayValidationError


@dataclass(frozen=True)
class HardwareInterfaceConfig:
    """Specification and configuration parameters for physical/simulated robot hardware interface."""

    robot_id: str
    transport_type: str = "simulator"  # "serial", "ethernet", or "simulator"
    mission_id: str | None = None
    serial_port: str | None = None  # e.g., "/dev/ttyUSB0" or "COM3"
    baudrate: int = 115200
    ethernet_host: str | None = None
    ethernet_port: int | None = None
    camera_id: str = "cam-front-01"
    camera_resolution: tuple[int, int] = (1920, 1080)
    target_frame_rate_fps: float = 15.0
    telemetry_timeout_s: float = 5.0
    frame_timeout_s: float = 10.0
    sensors_enabled: list[str] = field(
        default_factory=lambda: ["imu", "distance", "pressure", "water"]
    )


def validate_hardware_config(config: HardwareInterfaceConfig) -> None:
    """Validate a hardware interface configuration against protocol requirements.

    Raises RobotGatewayValidationError if configuration violates safety constraints.
    """
    if not config.robot_id or not config.robot_id.strip():
        raise RobotGatewayValidationError("robot_id must be a non-empty string.")

    if config.transport_type not in ("serial", "ethernet", "simulator"):
        raise RobotGatewayValidationError(
            f"Unsupported transport_type '{config.transport_type}'. Must be 'serial', 'ethernet', or 'simulator'."
        )

    if config.transport_type == "serial":
        if not config.serial_port or not config.serial_port.strip():
            raise RobotGatewayValidationError(
                "serial_port must be specified when transport_type is 'serial'."
            )
        if config.baudrate <= 0:
            raise RobotGatewayValidationError("baudrate must be a positive integer.")

    if config.transport_type == "ethernet":
        if not config.ethernet_host or not config.ethernet_host.strip():
            raise RobotGatewayValidationError(
                "ethernet_host must be specified when transport_type is 'ethernet'."
            )
        if config.ethernet_port is None or not (1 <= config.ethernet_port <= 65535):
            raise RobotGatewayValidationError(
                "ethernet_port must be a valid port number between 1 and 65535."
            )

    if config.camera_resolution[0] <= 0 or config.camera_resolution[1] <= 0:
        raise RobotGatewayValidationError("camera_resolution dimensions must be positive.")

    if config.target_frame_rate_fps <= 0.0:
        raise RobotGatewayValidationError("target_frame_rate_fps must be positive.")

    if config.telemetry_timeout_s <= 0.0:
        raise RobotGatewayValidationError("telemetry_timeout_s must be positive.")

    if config.frame_timeout_s <= 0.0:
        raise RobotGatewayValidationError("frame_timeout_s must be positive.")


def create_hardware_config(
    robot_id: str,
    transport_type: str = "simulator",
    **kwargs: Any,
) -> HardwareInterfaceConfig:
    """Construct and validate a HardwareInterfaceConfig object."""
    config = HardwareInterfaceConfig(
        robot_id=robot_id,
        transport_type=transport_type,
        **kwargs,
    )
    validate_hardware_config(config)
    return config
