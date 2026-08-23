"""Domain and Application Exceptions for Backend Mission Orchestration."""

from __future__ import annotations


class MissionOrchestrationError(Exception):
    """Base exception for all mission orchestration errors."""


class MissionNotFoundError(MissionOrchestrationError):
    """Raised when requested mission ID does not exist."""


class InvalidMissionLifecycleError(MissionOrchestrationError):
    """Raised when an illegal mission lifecycle state transition is attempted."""


class RobotMismatchError(MissionOrchestrationError):
    """Raised when telemetry or commands target a robot conflicting with mission registration."""


class MissionConflictError(MissionOrchestrationError):
    """Raised when a mission operation conflicts with existing active state."""
