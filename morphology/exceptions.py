"""Pipe Morphology Analysis Exceptions."""

from __future__ import annotations


class MorphologyError(Exception):
    """Base exception for all pipe morphology analysis errors."""


class InvalidCalibrationError(MorphologyError):
    """Raised when camera or sensor morphology calibration parameters are invalid."""


class InvalidDiameterValueError(MorphologyError):
    """Raised when an invalid or unphysical diameter measurement is encountered."""
