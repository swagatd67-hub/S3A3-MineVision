"""PipeVision Robot Localization Exceptions."""

from __future__ import annotations


class LocalizationError(Exception):
    """Base exception for all localization errors."""


class LocalizationInitializationError(LocalizationError):
    """Raised when localizer initialization fails."""


class LocalizationUpdateError(LocalizationError):
    """Raised when pose calculation or time integration fails."""
