"""PipeVision Robot Localization Data Models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LocalizationQuality(str, Enum):
    """Localization tracking quality indicator."""

    INITIALIZING = "INITIALIZING"
    TRACKING = "TRACKING"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class RobotPose:
    """Immutable Robot Pose in 2D pipe coordinate space.

    Units & Coordinates:
        timestamp: Timezone-aware UTC datetime of the telemetry sample
        distance_m: Primary longitudinal coordinate along pipe in meters (m)
        x: Cartesian position along pipe in meters (m) [x = distance_m]
        y: Cartesian lateral position across pipe in meters (m) [default 0.0]
        heading_rad: Relative yaw heading in radians (rad), integrated over time from IMU gyro
        heading_deg: Relative yaw heading in degrees (deg)
        quality: Localization quality indicator (LocalizationQuality)
        source: Metadata description of active sensor sources (str)
    """

    timestamp: datetime | None
    distance_m: float
    x: float
    y: float
    heading_rad: float
    heading_deg: float
    quality: LocalizationQuality
    source: str = "unknown"
