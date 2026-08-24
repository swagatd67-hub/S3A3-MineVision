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
    VideoIngestionResult,
)
from backend.app.services.inspection.sidecar import (
    load_global_directory_sidecar,
    load_sidecar_for_image,
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


def natural_sort_key(filename: str) -> list[int | str]:
    """Natural numeric sorting key function for filenames (e.g. 1.jpg < 2.jpg < 10.jpg)."""
    import re
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", filename)]


def _ensure_mission_exists(
    db: Session,
    mission_id: str,
    robot_id: str | None = None,
) -> Mission:
    """Ensure a Mission row exists in database; create it via MissionOrchestrator or as an offline mission."""
    from backend.app.models import Robot
    from backend.app.services.mission.models import MissionLifecycleState
    from backend.app.services.mission.orchestrator import MissionOrchestrator

    mission = db.get(Mission, mission_id)
    if mission is not None:
        return mission

    # If explicit robot_id is provided and registered in database, use standard orchestrator path
    if robot_id is not None:
        robot = db.get(Robot, robot_id)
        if robot is not None:
            orchestrator = MissionOrchestrator()
            return orchestrator.create_mission(db, robot_id=robot_id, mission_id=mission_id)

    # Offline mission with unavailable physical robot provenance - do NOT fabricate a fake Robot row
    effective_robot_id = robot_id or "OFFLINE"
    mission = Mission(
        mission_id=mission_id,
        robot_id=effective_robot_id,
        objective="INSPECT",
        status=MissionLifecycleState.CREATED.value,
        created_at=datetime.now(timezone.utc),
        notes="Offline media ingestion mission",
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)

    orchestrator = MissionOrchestrator()
    if mission_id not in orchestrator._twins:
        from digital_twin.synchronizer import DigitalTwinSynchronizer
        orchestrator._twins[mission_id] = DigitalTwinSynchronizer(
            mission_id=mission_id,
            robot_id=effective_robot_id,
        )
    return mission


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
        commit: bool = True,
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
            self.orchestrator.ingest_inspection_observation(db, frame.mission_id, obs, commit=commit)

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
                    commit=False,
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

        if succeeded:
            try:
                db.commit()
            except Exception as commit_exc:  # noqa: BLE001
                logger.error("Failed to commit batch ingestion for mission %s: %s", mission_id, commit_exc)
                db.rollback()
                failures.extend(
                    [
                        {
                            "frame_index": s.frame_index,
                            "frame_id": s.frame_id,
                            "error": f"Batch DB commit failed: {commit_exc}",
                            "error_type": "BatchCommitError",
                        }
                        for s in succeeded
                    ]
                )
                succeeded = []

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
        distance_start_m: float | None = None,
        distance_step_m: float | None = None,
        robot_id: str | None = None,
        camera_id: str | None = None,
        detector: Any | None = None,
        sewer_engine: Any | None = None,
        auto_create_mission: bool = True,
    ) -> BatchIngestionResult:
        """Offline workflow: Ingest an entire local directory of photo files with natural sorting & sidecar metadata."""
        dir_path = Path(directory_path).resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            raise InvalidImageContentError(f"Directory path does not exist or is not a directory: {directory_path}")

        global_defaults, per_frame_map = load_global_directory_sidecar(dir_path)

        eff_robot_id = robot_id or global_defaults.get("robot_id")
        eff_camera_id = camera_id or global_defaults.get("camera_id")

        if auto_create_mission:
            _ensure_mission_exists(db, mission_id, robot_id=eff_robot_id)

        image_files = sorted(
            [
                p for p in dir_path.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ],
            key=lambda p: natural_sort_key(p.name),
        )

        frames: list[CanonicalInspectionFrame] = []
        eff_step_m = (
            distance_step_m
            if distance_step_m is not None
            else global_defaults.get("distance_step_m")
        )
        eff_start_m = (
            distance_start_m
            if distance_start_m is not None
            else global_defaults.get("distance_start_m")
        )

        for idx, file_path in enumerate(image_files):
            sidecar = load_sidecar_for_image(file_path) or per_frame_map.get(file_path.name) or per_frame_map.get(file_path.stem)

            r_id = eff_robot_id or (sidecar.robot_id if sidecar else None)
            c_id = eff_camera_id or (sidecar.camera_id if sidecar else None)

            dist: float | None = None
            if eff_step_m is not None:
                start_m = eff_start_m if eff_start_m is not None else 0.0
                dist = start_m + (idx * eff_step_m)
            elif sidecar and sidecar.distance_m is not None:
                dist = sidecar.distance_m

            ts = sidecar.timestamp if sidecar else None
            pose = sidecar.pose if sidecar else None

            frames.append(
                CanonicalInspectionFrame(
                    mission_id=mission_id,
                    robot_id=r_id,
                    camera_id=c_id,
                    timestamp=ts,
                    source="photo",
                    frame_index=idx,
                    image_path=str(file_path),
                    distance_m=dist,
                    pose=pose,
                )
            )

        return self.ingest_batch(db, frames, detector=detector, sewer_engine=sewer_engine)

    def ingest_video_file(
        self,
        db: Session,
        video_path: str | Path,
        mission_id: str,
        frame_interval: int | None = None,
        target_fps: float | None = None,
        max_frames: int | None = None,
        start_timestamp: datetime | None = None,
        distance_start_m: float | None = None,
        distance_step_m: float | None = None,
        robot_id: str | None = None,
        camera_id: str | None = None,
        detector: Any | None = None,
        sewer_engine: Any | None = None,
        auto_create_mission: bool = True,
    ) -> VideoIngestionResult:
        """Offline workflow: Ingest an offline video file frame-by-frame with configurable sampling."""
        from datetime import timedelta

        import cv2

        v_path = Path(video_path).resolve()
        if not v_path.exists() or not v_path.is_file():
            raise InvalidImageContentError(f"Video file path does not exist or is not a file: {video_path}")

        supported_video_exts = {".mp4", ".avi", ".mov", ".mkv"}
        if v_path.suffix.lower() not in supported_video_exts:
            raise UnsupportedImageTypeError(f"Unsupported video extension '{v_path.suffix}'. Must be MP4, AVI, MOV, or MKV.")

        capture = cv2.VideoCapture(str(v_path))
        if not capture.isOpened():
            raise InvalidImageContentError(f"Failed to open video file: {video_path}")

        raw_fps = capture.get(cv2.CAP_PROP_FPS)
        fps = float(raw_fps) if raw_fps > 0 else 30.0
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_s = total_frames / fps if fps > 0 else 0.0

        if frame_interval is not None and frame_interval >= 1:
            step = frame_interval
        elif target_fps is not None and target_fps > 0:
            step = max(1, round(fps / target_fps))
        else:
            step = 1

        if auto_create_mission:
            _ensure_mission_exists(db, mission_id, robot_id=robot_id)

        raw_idx = 0
        sampled_count = 0
        succeeded: list[SingleIngestionResult] = []
        failures: list[dict[str, Any]] = []

        try:
            while True:
                ok, frame_bgr = capture.read()
                if not ok:
                    break

                current_idx = raw_idx
                raw_idx += 1

                if (current_idx % step) != 0:
                    continue

                if max_frames is not None and sampled_count >= max_frames:
                    break

                sampled_count += 1

                frame_ts: datetime | None = None
                if start_timestamp is not None:
                    frame_ts = start_timestamp + timedelta(seconds=current_idx / fps)

                frame_dist: float | None = None
                if distance_step_m is not None:
                    start_m = distance_start_m if distance_start_m is not None else 0.0
                    frame_dist = start_m + ((sampled_count - 1) * distance_step_m)

                success_encode, encoded_buf = cv2.imencode(".jpg", frame_bgr)
                if not success_encode or encoded_buf is None:
                    failures.append({
                        "frame_index": current_idx,
                        "error": "Failed to encode OpenCV BGR frame to JPEG",
                        "error_type": "EncodingError",
                    })
                    continue

                image_bytes = encoded_buf.tobytes()
                frame_id = f"{mission_id}_v_{current_idx:06d}"

                canonical_frame = CanonicalInspectionFrame(
                    mission_id=mission_id,
                    robot_id=robot_id,
                    camera_id=camera_id,
                    frame_id=frame_id,
                    timestamp=frame_ts,
                    source="video",
                    frame_index=current_idx,
                    image_bytes=image_bytes,
                    distance_m=frame_dist,
                )

                try:
                    res = self.ingest_frame(
                        db,
                        canonical_frame,
                        detector=detector,
                        sewer_engine=sewer_engine,
                    )
                    succeeded.append(res)
                except Exception as exc:  # noqa: BLE001
                    failures.append({
                        "frame_index": current_idx,
                        "frame_id": frame_id,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    })
        finally:
            capture.release()

        return VideoIngestionResult(
            mission_id=mission_id,
            video_path=str(v_path),
            total_video_frames=total_frames,
            sampled_frames=sampled_count,
            total_succeeded=len(succeeded),
            total_failed=len(failures),
            fps=fps,
            duration_s=duration_s,
            results=succeeded,
            failures=failures,
        )


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
    distance_start_m: float | None = None,
    distance_step_m: float | None = None,
    robot_id: str | None = None,
    camera_id: str | None = None,
    detector: Any | None = None,
    sewer_engine: Any | None = None,
    auto_create_mission: bool = True,
) -> BatchIngestionResult:
    """Module-level convenience wrapper for offline directory photo ingestion."""
    gateway = InspectionIngestionGateway()
    return gateway.ingest_photo_directory(
        db,
        directory_path,
        mission_id,
        distance_start_m=distance_start_m,
        distance_step_m=distance_step_m,
        robot_id=robot_id,
        camera_id=camera_id,
        detector=detector,
        sewer_engine=sewer_engine,
        auto_create_mission=auto_create_mission,
    )


def ingest_video_file(
    db: Session,
    video_path: str | Path,
    mission_id: str,
    frame_interval: int | None = None,
    target_fps: float | None = None,
    max_frames: int | None = None,
    start_timestamp: datetime | None = None,
    distance_start_m: float | None = None,
    distance_step_m: float | None = None,
    robot_id: str | None = None,
    camera_id: str | None = None,
    detector: Any | None = None,
    sewer_engine: Any | None = None,
    auto_create_mission: bool = True,
) -> VideoIngestionResult:
    """Module-level convenience wrapper for offline video file ingestion."""
    gateway = InspectionIngestionGateway()
    return gateway.ingest_video_file(
        db,
        video_path,
        mission_id,
        frame_interval=frame_interval,
        target_fps=target_fps,
        max_frames=max_frames,
        start_timestamp=start_timestamp,
        distance_start_m=distance_start_m,
        distance_step_m=distance_step_m,
        robot_id=robot_id,
        camera_id=camera_id,
        detector=detector,
        sewer_engine=sewer_engine,
        auto_create_mission=auto_create_mission,
    )
