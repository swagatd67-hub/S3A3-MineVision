"""Data models and enums for Robot Gateway / Hardware Adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from robot.localization.models import RobotPose


class GatewayConnectionState(str, Enum):
    """Lifecycle state of the Robot Gateway hardware connection."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    STREAMING = "STREAMING"
    DISCONNECTING = "DISCONNECTING"


class GatewayFailureReason(str, Enum):
    """Deterministic failure code for gateway connections and packet processing."""

    NONE = "NONE"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    TELEMETRY_TIMEOUT = "TELEMETRY_TIMEOUT"
    FRAME_TIMEOUT = "FRAME_TIMEOUT"
    INVALID_DATA = "INVALID_DATA"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    MISSION_MISMATCH = "MISSION_MISMATCH"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"


@dataclass(frozen=True)
class GatewayHealth:
    """Snapshot of Robot Gateway health, metrics, and connectivity."""

    connection_state: GatewayConnectionState
    failure_reason: GatewayFailureReason
    robot_id: str | None
    mission_id: str | None
    transport_type: str
    is_connected: bool
    is_healthy: bool
    last_telemetry_timestamp: datetime | None
    last_frame_timestamp: datetime | None
    telemetry_packet_count: int
    frame_count: int
    dropped_frame_count: int
    error_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert health snapshot to dictionary representation."""
        return {
            "connection_state": self.connection_state.value,
            "failure_reason": self.failure_reason.value,
            "robot_id": self.robot_id,
            "mission_id": self.mission_id,
            "transport_type": self.transport_type,
            "is_connected": self.is_connected,
            "is_healthy": self.is_healthy,
            "last_telemetry_timestamp": (
                self.last_telemetry_timestamp.isoformat()
                if self.last_telemetry_timestamp is not None
                else None
            ),
            "last_frame_timestamp": (
                self.last_frame_timestamp.isoformat()
                if self.last_frame_timestamp is not None
                else None
            ),
            "telemetry_packet_count": self.telemetry_packet_count,
            "frame_count": self.frame_count,
            "dropped_frame_count": self.dropped_frame_count,
            "error_count": self.error_count,
        }


@dataclass(frozen=True)
class HardwareFramePacket:
    """Raw camera frame packet received from physical robot or hardware capture driver."""

    camera_id: str
    image_bytes: bytes
    frame_index: int
    frame_id: str | None = None
    timestamp: datetime | str | None = None
    distance_m: float | None = None
    pose: RobotPose | None = None
    source: str = "live"
    metadata: dict[str, Any] | None = None
