"""Robot-Agnostic Photo / Inspection Ingestion Gateway Service.

Unified entry point for ingesting single photos, image batches, or video frames
into PipeVision's AI perception, observation fusion, mapping, and mission orchestration pipelines.
"""

from __future__ import annotations

import hashlib
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image
from sqlalchemy.orm import Session

from backend.app.models import Mission
from backend.app.services.inspection.exceptions import (
    InvalidImageContentError,
    UnsupportedImageTypeError,
)
from backend.app.services.inspection.fusion import (
    _parse_timestamp_to_utc,
    fuse_observations,
)
from backend.app.services.inspection.models import (
    BatchIngestionResult,
    CanonicalInspectionFrame,
    FusedInspectionObservation,
    InspectionFrameMetadata,
    SingleIngestionResult,
)
from backend.app.services.mission.exceptions import MissionNotFoundError
from backend.app.services.video.detection import (
    DetectionResult,
    NullDetector,
    analyze_image,
    analyze_image_with_sewer_ml,
)
from backend.app.services.video.frame_store import FrameMetadata, FrameMetadataStore
from backend.app.services.video.sewer_classifier import get_sewer_classifier_engine

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png"}
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def resolve_frame_id(
    mission_id: str,
    frame_index: int,
    provided_frame_id: str | None = None,
    image_bytes: bytes | None = None,
    filename: str | None = None,
) -> str:
    """Resolve frame ID. If provided_frame_id is present, preserve it. Otherwise generate deterministically."""
    if provided_frame_id and provided_frame_id.strip():
        return provided_frame_id.strip()

    if filename:
        key = f"{mission_id}:{frame_index}:{filename}"
    elif image_bytes:
        digest = hashlib.sha256(image_bytes).hexdigest()[:8]
        key = f"{mission_id}:{frame_index}:{digest}"
    else:
        key = f"{mission_id}:{frame_index}"

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    return f"frame-{frame_index:06d}-{digest}"


def extract_exif_timestamp(image_bytes: bytes) -> datetime | None:
    """Extract capture timestamp from EXIF metadata if present.

    Note: EXIF timestamps lacking explicit offset tags are assigned UTC by project capture-time policy.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            exif = img.getexif()
            if not exif:
                return None
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                if tag in ("DateTimeOriginal", "DateTime"):
                    val_str = str(value).strip()
                    parts = val_str.replace(":", " ").replace("-", " ").split()
                    if len(parts) >= 6:
                        year, month, day, hour, minute, second = (int(p) for p in parts[:6])
                        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def resolve_timestamp(
    explicit_ts: str | datetime | None,
    image_bytes: bytes | None = None,
) -> datetime | None:
    """Resolve capture timestamp: explicit input -> reliable EXIF capture date -> None (unavailable).

    Processing time is never fabricated as capture time.
    """
    parsed = _parse_timestamp_to_utc(explicit_ts)
    if parsed is not None:
        return parsed

    if image_bytes:
        exif_ts = extract_exif_timestamp(image_bytes)
        if exif_ts is not None:
            return exif_ts

    return None


class InspectionIngestionGateway:
    """Gateway service coordinating canonical image/frame ingestion into PipeVision."""

    def __init__(self, frame_store: FrameMetadataStore | None = None) -> None:
        from backend.app.services.mission.orchestrator import MissionOrchestrator

        self.frame_store = frame_store or FrameMetadataStore()
        self.orchestrator = MissionOrchestrator()

    def ingest_frame(
        self,
        db: Session,
        frame: CanonicalInspectionFrame,
        detector: Any | None = None,
        sewer_engine: Any | None = None,
    ) -> SingleIngestionResult:
        """Ingest a single canonical inspection frame through AI perception, fusion, and persistence."""
        # 1. Mission Existence Validation
        mission = db.get(Mission, frame.mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{frame.mission_id}' not found.")

        # 2. Image Content Resolution & Validation
        image_bytes: bytes
        extension = ".jpg"

        if frame.image_bytes is not None:
            image_bytes = frame.image_bytes
        elif frame.image_path is not None:
            path = Path(frame.image_path)
            if not path.is_absolute():
                path = Path.cwd() / path
            if not path.exists():
                raise InvalidImageContentError(f"Image path does not exist: {frame.image_path}")
            ext = path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                raise UnsupportedImageTypeError(f"Unsupported image extension '{ext}'. Must be JPG or PNG.")
            extension = ext if ext in {".jpg", ".jpeg", ".png"} else ".jpg"
            image_bytes = path.read_bytes()
        else:
            raise InvalidImageContentError("Either image_bytes or image_path must be provided.")

        if not image_bytes:
            raise InvalidImageContentError("Image payload cannot be empty.")

        # Validate image format via PIL
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                fmt = (img.format or "").upper()
                if fmt not in {"JPEG", "PNG"}:
                    raise UnsupportedImageTypeError(f"Unsupported image format '{fmt}'. Must be JPEG or PNG.")
                extension = ".png" if fmt == "PNG" else ".jpg"
        except UnsupportedImageTypeError:
            raise
        except Exception as exc:
            raise InvalidImageContentError(f"Failed to decode image content: {exc}") from exc

        # 3. Resolve Frame Identity and Timestamp
        frame_id = resolve_frame_id(
            mission_id=frame.mission_id,
            frame_index=frame.frame_index,
            provided_frame_id=frame.frame_id,
            image_bytes=image_bytes,
        )
        resolved_ts = resolve_timestamp(frame.timestamp, image_bytes)

        # 4. Save Image and Metadata in Frame Store
        saved_frame_path = self.frame_store.save_image(
            mission_id=frame.mission_id,
            frame_index=frame.frame_index,
            image_bytes=image_bytes,
            extension=extension,
        )
        self.frame_store.append(
            FrameMetadata(
                mission_id=frame.mission_id,
                frame_index=frame.frame_index,
                timestamp=resolved_ts,
                distance_m=frame.distance_m,
                source=frame.source,
                frame_path=saved_frame_path,
            )
        )

        abs_image_path = self.frame_store.image_path(frame.mission_id, frame.frame_index)
        if abs_image_path is None or not abs_image_path.exists():
            raise InvalidImageContentError(f"Failed to retrieve stored image path for mission {frame.mission_id}")

        # 5. Run AI Perception (YOLO + Sewer-ML)
        active_detector = detector if detector is not None else NullDetector()
        yolo_result: DetectionResult = analyze_image(abs_image_path, active_detector)

        active_sewer = sewer_engine if sewer_engine is not None else get_sewer_classifier_engine()
        sewer_result = analyze_image_with_sewer_ml(abs_image_path, engine=active_sewer)

        # 6. Inspection Observation Fusion
        frame_meta = InspectionFrameMetadata(
            mission_id=frame.mission_id,
            frame_index=frame.frame_index,
            timestamp=resolved_ts,
            distance_m=frame.distance_m,
            image_width=yolo_result.image_width,
            image_height=yolo_result.image_height,
        )

        fused_observations: list[FusedInspectionObservation] = fuse_observations(
            perception_input=[yolo_result, sewer_result],
            frame_metadata=frame_meta,
            robot_pose=frame.pose,
        )

        # 7. Persist via Mission Orchestration & Digital Twin Sync
        if frame.pose is not None:
            self.orchestrator.ingest_pose(db, frame.mission_id, frame.pose)

        for obs in fused_observations:
            self.orchestrator.ingest_inspection_observation(db, frame.mission_id, obs)

        if frame.distance_m is not None:
            self.orchestrator.update_mapping(db, frame.mission_id)
            self.orchestrator.update_morphology(db, frame.mission_id)

        return SingleIngestionResult(
            mission_id=frame.mission_id,
            frame_id=frame_id,
            frame_index=frame.frame_index,
            timestamp_iso=resolved_ts.isoformat() if resolved_ts is not None else None,
            source=frame.source,
            distance_m=frame.distance_m,
            frame_path=saved_frame_path,
            observations=fused_observations,
        )

    def ingest_batch(
        self,
        db: Session,
        frames: list[CanonicalInspectionFrame],
        detector: Any | None = None,
        sewer_engine: Any | None = None,
    ) -> BatchIngestionResult:
        """Ingest a batch of canonical frames deterministically with partial failure resilience."""
        if not frames:
            return BatchIngestionResult(
                mission_id="unknown",
                total_submitted=0,
                total_succeeded=0,
                total_failed=0,
                results=[],
                failures=[],
            )

        mission_id = frames[0].mission_id
        # Sort frames deterministically by frame_index
        sorted_frames = sorted(frames, key=lambda f: (f.frame_index, f.frame_id or ""))

        succeeded: list[SingleIngestionResult] = []
        failures: list[dict[str, Any]] = []

        active_detector = detector if detector is not None else NullDetector()
        active_sewer = sewer_engine if sewer_engine is not None else get_sewer_classifier_engine()

        for frame in sorted_frames:
            try:
                res = self.ingest_frame(
                    db,
                    frame,
                    detector=active_detector,
                    sewer_engine=active_sewer,
                )
                succeeded.append(res)
            except (
                UnsupportedImageTypeError,
                InvalidImageContentError,
                MissionNotFoundError,
                ValueError,
                OSError,
                RuntimeError,
            ) as exc:
                logger.warning(
                    "Frame ingestion failed for mission %s frame_index %d: %s",
                    frame.mission_id,
                    frame.frame_index,
                    exc,
                )
                failures.append(
                    {
                        "frame_index": frame.frame_index,
                        "frame_id": frame.frame_id,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
                )

        return BatchIngestionResult(
            mission_id=mission_id,
            total_submitted=len(sorted_frames),
            total_succeeded=len(succeeded),
            total_failed=len(failures),
            results=succeeded,
            failures=failures,
        )

    def ingest_photo_directory(
        self,
        db: Session,
        directory_path: str | Path,
        mission_id: str,
        distance_step_m: float | None = None,
        robot_id: str | None = None,
        camera_id: str | None = None,
        detector: Any | None = None,
        sewer_engine: Any | None = None,
    ) -> BatchIngestionResult:
        """Offline workflow: Ingest an entire local directory of photo files."""
        dir_path = Path(directory_path).resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            raise InvalidImageContentError(f"Directory path does not exist or is not a directory: {directory_path}")

        image_files = sorted(
            [
                p for p in dir_path.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ],
            key=lambda p: p.name,
        )

        frames: list[CanonicalInspectionFrame] = []
        for idx, file_path in enumerate(image_files):
            dist = (idx * distance_step_m) if distance_step_m is not None else None
            frames.append(
                CanonicalInspectionFrame(
                    mission_id=mission_id,
                    robot_id=robot_id,
                    camera_id=camera_id,
                    source="photo",
                    frame_index=idx,
                    image_path=str(file_path),
                    distance_m=dist,
                )
            )

        return self.ingest_batch(db, frames, detector=detector, sewer_engine=sewer_engine)


def ingest_inspection_frame(
    db: Session,
    frame: CanonicalInspectionFrame,
    detector: Any | None = None,
    sewer_engine: Any | None = None,
) -> SingleIngestionResult:
    """Module-level convenience wrapper for single frame ingestion."""
    gateway = InspectionIngestionGateway()
    return gateway.ingest_frame(db, frame, detector=detector, sewer_engine=sewer_engine)


def ingest_inspection_batch(
    db: Session,
    frames: list[CanonicalInspectionFrame],
    detector: Any | None = None,
    sewer_engine: Any | None = None,
) -> BatchIngestionResult:
    """Module-level convenience wrapper for batch frame ingestion."""
    gateway = InspectionIngestionGateway()
    return gateway.ingest_batch(db, frames, detector=detector, sewer_engine=sewer_engine)


def ingest_photo_directory(
    db: Session,
    directory_path: str | Path,
    mission_id: str,
    distance_step_m: float | None = None,
    robot_id: str | None = None,
    camera_id: str | None = None,
    detector: Any | None = None,
    sewer_engine: Any | None = None,
) -> BatchIngestionResult:
    """Module-level convenience wrapper for offline directory photo ingestion."""
    gateway = InspectionIngestionGateway()
    return gateway.ingest_photo_directory(
        db,
        directory_path,
        mission_id,
        distance_step_m=distance_step_m,
        robot_id=robot_id,
        camera_id=camera_id,
        detector=detector,
        sewer_engine=sewer_engine,
    )
