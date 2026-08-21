"""Inspection Observation Fusion Exceptions."""

from __future__ import annotations


class InspectionFusionError(Exception):
    """Base exception for all inspection observation fusion errors."""


class InvalidPerceptionInputError(InspectionFusionError):
    """Raised when raw perception input is invalid or unsupported."""


class DistanceConflictError(InspectionFusionError):
    """Raised when distance conflict resolution fails under strict policy."""
