"""Custom Exceptions for 3D Pipe Reconstruction Module."""

from __future__ import annotations


class ReconstructionError(Exception):
    """Base exception for all 3D reconstruction errors."""


class InsufficientDataError(ReconstructionError):
    """Raised when frame count or metadata is insufficient for 3D reconstruction."""


class CalibrationError(ReconstructionError):
    """Raised when camera calibration data is invalid or missing when strictly required."""


class CoordinateTransformError(ReconstructionError):
    """Raised when coordinate frame transformation fails."""


class ScaleEstimationError(ReconstructionError):
    """Raised when metric scale cannot be estimated."""
