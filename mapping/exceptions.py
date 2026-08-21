"""Pipe Inspection Mapping Exceptions."""

from __future__ import annotations


class MappingError(Exception):
    """Base exception for all pipe inspection mapping errors."""


class MixedMissionError(MappingError):
    """Raised when input observations contain multiple distinct mission IDs without explicit filtering."""


class InvalidObservationError(MappingError):
    """Raised when an observation cannot be processed into a valid map feature."""
