"""Inspection Observation Fusion Exceptions."""

from __future__ import annotations


class InspectionFusionError(Exception):
    """Base exception for all inspection observation fusion errors."""


class InvalidPerceptionInputError(InspectionFusionError):
    """Raised when raw perception input is invalid or unsupported."""


class DistanceConflictError(InspectionFusionError):
    """Raised when distance conflict resolution fails under strict policy."""


class UnsupportedImageTypeError(InspectionFusionError):
    """Raised when an uploaded file is not a supported image type (JPEG/PNG)."""


class InvalidImageContentError(InspectionFusionError):
    """Raised when image bytes are empty or corrupted."""


class MalformedMetadataError(InspectionFusionError):
    """Raised when metadata payload fails validation."""


class FrameProcessingError(InspectionFusionError):
    """Raised when image processing or AI perception fails for a frame."""
