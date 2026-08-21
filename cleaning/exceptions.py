"""Exceptions for Pipe Cleaning Operations & Effectiveness Analysis."""

from __future__ import annotations


class CleaningError(Exception):
    """Base exception for all pipe cleaning domain errors."""


class CleaningStateError(CleaningError):
    """Raised when an operation transition violates the cleaning state machine."""


class CleaningConcurrencyError(CleaningError):
    """Raised when attempting to start multiple active cleaning operations on the same mission."""


class CleaningNotFoundError(CleaningError):
    """Raised when referencing a non-existent cleaning operation."""


class InvalidOperationError(CleaningError):
    """Raised when a cleaning operation definition contains invalid arguments or boundaries."""


class IncompatibleComparisonError(CleaningError):
    """Raised when before/after datasets cannot be compared for effectiveness."""
