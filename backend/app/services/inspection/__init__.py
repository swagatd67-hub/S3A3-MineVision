"""PipeVision Inspection Observation Fusion Package."""

from backend.app.services.inspection.exceptions import (
    DistanceConflictError,
    FrameProcessingError,
    InspectionFusionError,
    InvalidImageContentError,
    InvalidPerceptionInputError,
    MalformedMetadataError,
    UnsupportedImageTypeError,
)
from backend.app.services.inspection.fusion import (
    adapt_perception_input,
    fuse_observations,
)
from backend.app.services.inspection.gateway import (
    InspectionIngestionGateway,
    ingest_inspection_batch,
    ingest_inspection_frame,
    ingest_photo_directory,
)
from backend.app.services.inspection.models import (
    BatchIngestionResult,
    BoundingBox,
    CanonicalInspectionFrame,
    FusedInspectionObservation,
    InspectionFrameMetadata,
    RawPerceptionItem,
    SingleIngestionResult,
)

__all__ = [
    "BatchIngestionResult",
    "BoundingBox",
    "CanonicalInspectionFrame",
    "DistanceConflictError",
    "FrameProcessingError",
    "FusedInspectionObservation",
    "InspectionFrameMetadata",
    "InspectionFusionError",
    "InspectionIngestionGateway",
    "InvalidImageContentError",
    "InvalidPerceptionInputError",
    "MalformedMetadataError",
    "RawPerceptionItem",
    "SingleIngestionResult",
    "UnsupportedImageTypeError",
    "adapt_perception_input",
    "fuse_observations",
    "ingest_inspection_batch",
    "ingest_inspection_frame",
    "ingest_photo_directory",
]
