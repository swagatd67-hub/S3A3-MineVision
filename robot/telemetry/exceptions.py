"""Telemetry Exception Hierarchy."""

from __future__ import annotations


class TelemetryError(Exception):
    """Base exception for all telemetry errors."""


class TelemetryParseError(TelemetryError):
    """Raised when raw telemetry payload cannot be parsed as valid structure/JSON."""


class TelemetryValidationError(TelemetryError):
    """Raised when parsed telemetry payload violates schema, types, or bounds constraints."""
