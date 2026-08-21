"""Exceptions for PipeVision Digital Twin Domain."""

from __future__ import annotations


class DigitalTwinError(Exception):
    """Base exception for all digital twin domain errors."""


class MissionMismatchError(DigitalTwinError):
    """Raised when attempting to update digital twin with data from a different mission."""


class StaleUpdateError(DigitalTwinError):
    """Raised when attempting to overwrite newer twin state with older timestamped data."""


class InvalidTwinStateError(DigitalTwinError):
    """Raised when digital twin state parameters violate domain constraints."""
