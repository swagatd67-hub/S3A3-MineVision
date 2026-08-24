"""Exceptions for PipeVision Robot Gateway and Hardware Adapter."""

from __future__ import annotations


class RobotGatewayError(Exception):
    """Base exception for all robot gateway errors."""


class RobotGatewayConnectionError(RobotGatewayError):
    """Raised when establishing or operating a gateway connection fails."""


class RobotGatewayValidationError(RobotGatewayError):
    """Raised when payload or identity validation fails in the gateway."""


class RobotGatewayTimeoutError(RobotGatewayError):
    """Raised when telemetry or frame timeout is exceeded."""


class RobotGatewayStateError(RobotGatewayError):
    """Raised when an operation is invalid for current gateway state."""
