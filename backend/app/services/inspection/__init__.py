"""PipeVision Inspection Observation Fusion Package."""

from backend.app.services.inspection.exceptions import (
    DistanceConflictError,
    InspectionFusionError,
    InvalidPerceptionInputError,
)
from backend.app.services.inspection.fusion import (
    adapt_perception_input,
    fuse_observations,
)
from backend.app.services.inspection.models import (
    BoundingBox,
    FusedInspectionObservation,
    InspectionFrameMetadata,
    RawPerceptionItem,
)

__all__ = [
    "BoundingBox",
    "DistanceConflictError",
    "FusedInspectionObservation",
    "InspectionFrameMetadata",
    "InspectionFusionError",
    "InvalidPerceptionInputError",
    "RawPerceptionItem",
    "adapt_perception_input",
    "fuse_observations",
]
