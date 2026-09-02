import logging
import math
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.services.inspection import (
    CanonicalInspectionFrame,
    InspectionIngestionGateway,
    InvalidImageContentError,
    UnsupportedImageTypeError,
)
from backend.app.services.mission.exceptions import MissionNotFoundError
from backend.app.services.video.detection import (
    NullDetector,
    analyze_image,
    analyze_image_with_sewer_ml,
    load_detector,
    result_to_dict,
)
from backend.app.services.video.frame_store import (
    FrameMetadata,
    FrameMetadataStore,
)
from backend.app.services.video.hardware_ingestion import (
    HardwareIngestionManager,
)
from backend.app.services.video.recording import RecordingManager
from backend.app.services.video.sewer_classifier import (
    get_sewer_classifier_engine,
)
from backend.app.services.video.snapshot_store import (
    SnapshotRecord,
    SnapshotStore,
)
from backend.app.services.video.source import ESP32CAMSource
from backend.app.services.video.streaming import (
    esp32cam_mjpeg_proxy,
    mjpeg_frame_generator,
)
from robot.localization.models import LocalizationQuality, RobotPose

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video", tags=["video"])

frame_store = FrameMetadataStore()
snapshot_store = SnapshotStore()
recording_manager = RecordingManager()
pipeline_detector = NullDetector()
ingestion_gateway = InspectionIngestionGateway()
hardware_ingestion_manager = HardwareIngestionManager.get_instance()


class FrameMetadataRequest(BaseModel):
    mission_id: str = Field(min_length=1, max_length=64)
    frame_index: int = Field(ge=0)
    timestamp: datetime
    distance_m: float
    source: str = Field(min_length=1, max_length=128)
    frame_path: str | None = Field(default=None, max_length=512)


class CreateSnapshotRequest(BaseModel):
    frame_index: int = Field(ge=0)
    camera_id: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=512)


class StartRecordingRequest(BaseModel):
    camera_id: str | None = Field(default=None, max_length=64)


@router.get("/health")
def video_health() -> dict:
    settings = get_settings()
    return {
        "service": "video",
        "status": "ready",
        "supported_sources": ["simulator", "esp32cam"],
        "configured_source": settings.camera_source_type,
        "image_storage": True,
        "detection_pipeline": True,
        "snapshots": True,
        "streaming": True,
        "recording": True,
    }


@router.post("/frames", status_code=201)
def store_frame_metadata(payload: FrameMetadataRequest) -> dict:
    metadata = frame_store.append(
        FrameMetadata(
            mission_id=payload.mission_id,
            frame_index=payload.frame_index,
            timestamp=payload.timestamp,
            distance_m=payload.distance_m,
            source=payload.source,
            frame_path=payload.frame_path,
        )
    )

    return {
        "stored": True,
        "frame": {
            "mission_id": metadata.mission_id,
            "frame_index": metadata.frame_index,
            "timestamp": (
                metadata.timestamp.isoformat()
                if metadata.timestamp is not None
                else None
            ),
            "distance_m": metadata.distance_m,
            "source": metadata.source,
            "frame_path": metadata.frame_path,
        },
    }


@router.post("/frames/image", status_code=201)
async def store_frame_image(
    mission_id: Annotated[str, Form(min_length=1, max_length=64)],
    frame_index: Annotated[int, Form(ge=0)],
    timestamp: Annotated[datetime, Form()],
    distance_m: Annotated[float, Form()],
    source: Annotated[str, Form(min_length=1, max_length=128)],
    image: Annotated[UploadFile, File()],
) -> dict:
    content_type = image.content_type or ""

    if content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(
            status_code=415,
            detail="only JPEG and PNG images are supported",
        )

    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="empty_image",
        )

    extension = ".png" if content_type == "image/png" else ".jpg"

    frame_path = frame_store.save_image(
        mission_id=mission_id,
        frame_index=frame_index,
        image_bytes=image_bytes,
        extension=extension,
    )

    metadata = frame_store.append(
        FrameMetadata(
            mission_id=mission_id,
            frame_index=frame_index,
            timestamp=timestamp,
            distance_m=distance_m,
            source=source,
            frame_path=frame_path,
        )
    )

    return {
        "stored": True,
        "image_bytes": len(image_bytes),
        "frame": {
            "mission_id": metadata.mission_id,
            "frame_index": metadata.frame_index,
            "timestamp": (
                metadata.timestamp.isoformat()
                if metadata.timestamp is not None
                else None
            ),
            "distance_m": metadata.distance_m,
            "source": metadata.source,
            "frame_path": metadata.frame_path,
        },
    }


@router.get("/missions/{mission_id}/frames")
def list_frame_metadata(
    mission_id: str,
    limit: int = Query(default=100, ge=1, le=5000),
) -> dict:
    records = frame_store.list(mission_id, limit=limit)

    return {
        "mission_id": mission_id,
        "count": len(records),
        "frames": [
            {
                "mission_id": item.mission_id,
                "frame_index": item.frame_index,
                "timestamp": (
                    item.timestamp.isoformat()
                    if item.timestamp is not None
                    else None
                ),
                "distance_m": item.distance_m,
                "source": item.source,
                "frame_path": item.frame_path,
            }
            for item in records
        ],
    }


@router.get("/missions/{mission_id}/frames/{frame_index}")
def get_frame_metadata(
    mission_id: str,
    frame_index: int,
) -> dict:
    record = frame_store.get(mission_id, frame_index)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="frame_not_found",
        )

    return {
        "mission_id": mission_id,
        "frame_index": record.frame_index,
        "timestamp": (
            record.timestamp.isoformat()
            if record.timestamp is not None
            else None
        ),
        "distance_m": record.distance_m,
        "source": record.source,
        "frame_path": record.frame_path,
    }


@router.get("/missions/{mission_id}/frames/{frame_index}/image")
def get_frame_image(
    mission_id: str,
    frame_index: int,
):
    try:
        path = frame_store.image_path(
            mission_id,
            frame_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if path is None or not path.exists():
        raise HTTPException(
            status_code=404,
            detail="frame_image_not_found",
        )

    return FileResponse(path)


@router.post("/missions/{mission_id}/frames/{frame_index}/detect")
def detect_frame(
    mission_id: str,
    frame_index: int,
    model: str = Query(default="null"),
    confidence: float = Query(default=0.25, ge=0.0, le=1.0),
) -> dict:
    record = frame_store.get(
        mission_id,
        frame_index,
    )

    if record is None or not record.frame_path:
        raise HTTPException(
            status_code=404,
            detail="frame_not_found",
        )

    try:
        image_path = frame_store.image_path(
            mission_id,
            frame_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if image_path is None or not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail="frame_image_not_found",
        )

    detector = (
        pipeline_detector
        if model == "null"
        else load_detector(
            model,
            confidence_threshold=confidence,
        )
    )

    result = analyze_image(
        image_path,
        detector,
    )

    return {
        "mission_id": mission_id,
        "frame_index": frame_index,
        "timestamp": (
            record.timestamp.isoformat()
            if record.timestamp is not None
            else None
        ),
        "distance_m": record.distance_m,
        "source": record.source,
        **result_to_dict(result),
    }


@router.post("/missions/{mission_id}/frames/{frame_index}/classify_sewer")
def classify_sewer_frame(
    mission_id: str,
    frame_index: int,
) -> dict:
    record = frame_store.get(
        mission_id,
        frame_index,
    )

    if record is None or not record.frame_path:
        raise HTTPException(
            status_code=404,
            detail="frame_not_found",
        )

    try:
        image_path = frame_store.image_path(
            mission_id,
            frame_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if image_path is None or not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail="frame_image_not_found",
        )

    engine = get_sewer_classifier_engine()
    result = analyze_image_with_sewer_ml(
        image_path,
        engine=engine,
    )

    return {
        "mission_id": mission_id,
        "frame_index": frame_index,
        "timestamp": (
            record.timestamp.isoformat()
            if record.timestamp is not None
            else None
        ),
        "distance_m": record.distance_m,
        "source": record.source,
        **result.to_dict(),
    }


# ============================================================================
# SNAPSHOT ENDPOINTS
# ============================================================================


@router.post("/missions/{mission_id}/snapshots", status_code=201)
def create_snapshot(
    mission_id: str,
    payload: CreateSnapshotRequest,
) -> dict:
    """Create a persistent media snapshot from an existing mission frame."""
    frame_record = frame_store.get(mission_id, payload.frame_index)
    if frame_record is None:
        raise HTTPException(status_code=404, detail="frame_not_found")

    try:
        image_path = frame_store.image_path(mission_id, payload.frame_index)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if image_path is None or not image_path.exists():
        raise HTTPException(status_code=404, detail="frame_image_not_found")

    snapshot_id = f"snap-{payload.frame_index:06d}-{uuid.uuid4().hex[:6]}"
    image_url = f"/api/v1/video/missions/{mission_id}/snapshots/{snapshot_id}/image"

    rec = snapshot_store.create(
        SnapshotRecord(
            snapshot_id=snapshot_id,
            mission_id=mission_id,
            frame_index=payload.frame_index,
            timestamp=frame_record.timestamp,
            distance_m=frame_record.distance_m,
            camera_id=payload.camera_id,
            frame_path=frame_record.frame_path,
            image_url=image_url,
            notes=payload.notes,
        )
    )

    return {
        "snapshot_id": rec.snapshot_id,
        "mission_id": rec.mission_id,
        "frame_index": rec.frame_index,
        "timestamp": rec.timestamp.isoformat() if rec.timestamp is not None else None,
        "distance_m": rec.distance_m,
        "camera_id": rec.camera_id,
        "image_url": rec.image_url,
        "notes": rec.notes,
        "created_at": rec.created_at.isoformat() if rec.created_at is not None else None,
    }


@router.get("/missions/{mission_id}/snapshots")
def list_snapshots(
    mission_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    """List persistent media snapshots for a mission."""
    records = snapshot_store.list(mission_id, limit=limit)
    return {
        "mission_id": mission_id,
        "count": len(records),
        "snapshots": [
            {
                "snapshot_id": r.snapshot_id,
                "mission_id": r.mission_id,
                "frame_index": r.frame_index,
                "timestamp": r.timestamp.isoformat() if r.timestamp is not None else None,
                "distance_m": r.distance_m,
                "camera_id": r.camera_id,
                "image_url": r.image_url,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at is not None else None,
            }
            for r in records
        ],
    }


@router.get("/missions/{mission_id}/snapshots/{snapshot_id}")
def get_snapshot(
    mission_id: str,
    snapshot_id: str,
) -> dict:
    """Retrieve metadata for a specific persistent media snapshot."""
    r = snapshot_store.get(mission_id, snapshot_id)
    if r is None:
        raise HTTPException(status_code=404, detail="snapshot_not_found")

    return {
        "snapshot_id": r.snapshot_id,
        "mission_id": r.mission_id,
        "frame_index": r.frame_index,
        "timestamp": r.timestamp.isoformat() if r.timestamp is not None else None,
        "distance_m": r.distance_m,
        "camera_id": r.camera_id,
        "image_url": r.image_url,
        "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at is not None else None,
    }


@router.get("/missions/{mission_id}/snapshots/{snapshot_id}/image")
def get_snapshot_image(
    mission_id: str,
    snapshot_id: str,
):
    """Retrieve the image binary for a specific persistent media snapshot."""
    r = snapshot_store.get(mission_id, snapshot_id)
    if r is None:
        raise HTTPException(status_code=404, detail="snapshot_not_found")

    try:
        path = frame_store.image_path(mission_id, r.frame_index)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="snapshot_image_not_found")

    return FileResponse(path)


@router.delete("/missions/{mission_id}/snapshots/{snapshot_id}")
def delete_snapshot(
    mission_id: str,
    snapshot_id: str,
) -> dict:
    """Delete a persistent media snapshot record."""
    deleted = snapshot_store.delete(mission_id, snapshot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    return {"deleted": True, "snapshot_id": snapshot_id}


# ============================================================================
# STREAMING ENDPOINTS
# ============================================================================


@router.get("/missions/{mission_id}/stream")
def get_live_stream(
    mission_id: str,
    camera_id: str = Query(default="cam-01"),
    fps: float = Query(default=10.0, ge=1.0, le=60.0),
    loop: bool = Query(default=True),
):
    """Stream live/simulated video feed as an MJPEG multipart response.

    Note: Exposes stored or simulated mission frames as a development/playback stream
    when dedicated hardware video sources are offline.
    """
    settings = get_settings()
    if settings.camera_source_type == "esp32cam":
        # URL and endpoint shape are deployment configuration; this backend
        # proxies the bytes without assuming a particular ESP32-CAM firmware.
        source = ESP32CAMSource(
            url=settings.esp32_cam_url or "",
            snapshot_url=settings.esp32_cam_snapshot_url,
            timeout_s=settings.esp32_cam_timeout_s,
        )
        return StreamingResponse(
            esp32cam_mjpeg_proxy(
                source,
                fps=fps,
                fallback_text=f"ESP32-CAM OFFLINE [{camera_id}]",
            ),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    return StreamingResponse(
        mjpeg_frame_generator(
            mission_id=mission_id,
            frame_store=frame_store,
            camera_id=camera_id,
            fps=fps,
            loop=loop,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.websocket("/missions/{mission_id}/ws/stream")
async def websocket_stream(
    websocket: WebSocket,
    mission_id: str,
    fps: float = Query(default=10.0, ge=1.0, le=60.0),
):
    """WebSocket endpoint for real-time streaming frame ingestion/playback."""
    await websocket.accept()
    settings = get_settings()
    if settings.camera_source_type == "esp32cam":
        source = ESP32CAMSource(
            settings.esp32_cam_url or "",
            timeout_s=settings.esp32_cam_timeout_s,
        )
        try:
            async for chunk in esp32cam_mjpeg_proxy(source):
                await websocket.send_bytes(chunk)
        except WebSocketDisconnect:
            logger.debug("ESP32-CAM websocket client disconnected for mission '%s'", mission_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug("ESP32-CAM websocket exception for mission '%s': %s", mission_id, exc)
        return

    generator = mjpeg_frame_generator(
        mission_id=mission_id,
        frame_store=frame_store,
        fps=fps,
    )
    try:
        async for chunk in generator:
            await websocket.send_bytes(chunk)
    except WebSocketDisconnect:
        logger.debug("WebSocket stream client disconnected for mission '%s'", mission_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("WebSocket stream exception for mission '%s': %s", mission_id, exc)


# ============================================================================
# RECORDING SESSION ENDPOINTS
# ============================================================================


@router.post("/missions/{mission_id}/recording/start", status_code=201)
def start_recording(
    mission_id: str,
    payload: StartRecordingRequest | None = None,
) -> dict:
    """Start a recording session for a mission."""
    camera_id = payload.camera_id if payload else None
    try:
        session = recording_manager.start_recording(mission_id, camera_id=camera_id)
        return {
            "recording_id": session.recording_id,
            "mission_id": session.mission_id,
            "camera_id": session.camera_id,
            "start_time": session.start_time.isoformat(),
            "stop_time": None,
            "status": session.status,
            "frame_count": session.frame_count,
            "media_location": session.media_location,
        }
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/missions/{mission_id}/recording/stop")
def stop_recording(
    mission_id: str,
    recording_id: str | None = Query(default=None),
) -> dict:
    """Stop an active recording session for a mission."""
    try:
        session = recording_manager.stop_recording(
            mission_id, recording_id=recording_id, frame_store=frame_store
        )
        return {
            "recording_id": session.recording_id,
            "mission_id": session.mission_id,
            "camera_id": session.camera_id,
            "start_time": session.start_time.isoformat(),
            "stop_time": (
                session.stop_time.isoformat()
                if session.stop_time is not None
                else None
            ),
            "status": session.status,
            "frame_count": session.frame_count,
            "media_location": session.media_location,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/missions/{mission_id}/recording/status")
def get_recording_status(
    mission_id: str,
) -> dict:
    """Get recording status for a mission."""
    session = recording_manager.get_status(mission_id)
    if session is None:
        return {
            "mission_id": mission_id,
            "is_recording": False,
            "session": None,
        }

    return {
        "mission_id": mission_id,
        "is_recording": session.status == "RECORDING",
        "session": {
            "recording_id": session.recording_id,
            "mission_id": session.mission_id,
            "camera_id": session.camera_id,
            "start_time": session.start_time.isoformat(),
            "stop_time": (
                session.stop_time.isoformat()
                if session.stop_time is not None
                else None
            ),
            "status": session.status,
            "frame_count": session.frame_count,
            "media_location": session.media_location,
        },
    }


@router.get("/missions/{mission_id}/recordings")
def list_recordings(
    mission_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    """List recording sessions for a mission."""
    records = recording_manager.list_recordings(mission_id, limit=limit)
    return {
        "mission_id": mission_id,
        "count": len(records),
        "recordings": [
            {
                "recording_id": r.recording_id,
                "mission_id": r.mission_id,
                "camera_id": r.camera_id,
                "start_time": r.start_time.isoformat(),
                "stop_time": (
                    r.stop_time.isoformat() if r.stop_time is not None else None
                ),
                "status": r.status,
                "frame_count": r.frame_count,
                "media_location": r.media_location,
            }
            for r in records
        ],
    }


@router.get("/missions/{mission_id}/recordings/{recording_id}")
def get_recording(
    mission_id: str,
    recording_id: str,
) -> dict:
    """Retrieve details for a specific recording session."""
    r = recording_manager.get_recording(mission_id, recording_id)
    if r is None:
        raise HTTPException(status_code=404, detail="recording_not_found")

    return {
        "recording_id": r.recording_id,
        "mission_id": r.mission_id,
        "camera_id": r.camera_id,
        "start_time": r.start_time.isoformat(),
        "stop_time": r.stop_time.isoformat() if r.stop_time is not None else None,
        "status": r.status,
        "frame_count": r.frame_count,
        "media_location": r.media_location,
    }


# ============================================================================
# INGESTION ENDPOINTS (EXISTING)
# ============================================================================


class DirectoryIngestionRequest(BaseModel):
    mission_id: str = Field(min_length=1, max_length=64)
    directory_path: str = Field(min_length=1, max_length=512)
    distance_start_m: float | None = Field(default=None)
    distance_step_m: float | None = Field(default=None, ge=0.0)
    robot_id: str | None = Field(default=None, max_length=64)
    camera_id: str | None = Field(default=None, max_length=64)
    auto_create_mission: bool = Field(default=True)


class VideoIngestionRequest(BaseModel):
    mission_id: str = Field(min_length=1, max_length=64)
    video_path: str = Field(min_length=1, max_length=512)
    frame_interval: int | None = Field(default=None, ge=1)
    target_fps: float | None = Field(default=None, gt=0.0)
    max_frames: int | None = Field(default=None, ge=1)
    start_timestamp: datetime | None = Field(default=None)
    distance_start_m: float | None = Field(default=None)
    distance_step_m: float | None = Field(default=None, ge=0.0)
    robot_id: str | None = Field(default=None, max_length=64)
    camera_id: str | None = Field(default=None, max_length=64)
    auto_create_mission: bool = Field(default=True)


ALLOWED_INGEST_ROOT = get_settings().media_import_root.resolve()


@router.post("/ingest/image", status_code=201)
async def ingest_single_image(
    mission_id: Annotated[str, Form(min_length=1, max_length=64)],
    image: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    robot_id: Annotated[str | None, Form(max_length=64)] = None,
    camera_id: Annotated[str | None, Form(max_length=64)] = None,
    frame_index: Annotated[int | None, Form(ge=0)] = None,
    frame_id: Annotated[str | None, Form(max_length=128)] = None,
    timestamp: Annotated[datetime | None, Form()] = None,
    source: Annotated[str, Form(min_length=1, max_length=128)] = "photo",
    distance_m: Annotated[float | None, Form()] = None,
    x: Annotated[float | None, Form()] = None,
    y: Annotated[float | None, Form()] = None,
    heading_deg: Annotated[float | None, Form()] = None,
) -> dict:
    """Ingest a single photo or frame into PipeVision's perception, fusion, and persistence pipelines."""
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="empty_image")

    settings = get_settings()
    if len(image_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image upload size exceeds maximum allowed limit of {settings.max_upload_size_bytes} bytes",
        )

    pose: RobotPose | None = None
    if x is not None and y is not None and heading_deg is not None:
        pose = RobotPose(
            timestamp=timestamp,
            distance_m=distance_m if distance_m is not None else x,
            x=x,
            y=y,
            heading_rad=math.radians(heading_deg),
            heading_deg=heading_deg,
            quality=LocalizationQuality.TRACKING,
            source="photo_api",
        )

    canonical_frame = CanonicalInspectionFrame(
        mission_id=mission_id,
        robot_id=robot_id,
        frame_id=frame_id,
        camera_id=camera_id,
        timestamp=timestamp,
        source=source,
        frame_index=frame_index if frame_index is not None else 0,
        image_bytes=image_bytes,
        distance_m=distance_m,
        pose=pose,
    )

    try:
        res = ingestion_gateway.ingest_frame(db, canonical_frame)
        return res.to_dict()
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnsupportedImageTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except InvalidImageContentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Ingestion failed: {exc}"
        ) from exc


@router.post("/ingest/batch", status_code=201)
async def ingest_batch_images(
    mission_id: Annotated[str, Form(min_length=1, max_length=64)],
    images: Annotated[list[UploadFile], File()],
    db: Annotated[Session, Depends(get_db)],
    robot_id: Annotated[str | None, Form(max_length=64)] = None,
    camera_id: Annotated[str | None, Form(max_length=64)] = None,
    source: Annotated[str, Form(min_length=1, max_length=128)] = "photo",
    distance_start_m: Annotated[float | None, Form()] = None,
    distance_step_m: Annotated[float | None, Form()] = None,
) -> dict:
    """Ingest a batch of photos or frames into PipeVision."""
    if not images:
        raise HTTPException(status_code=400, detail="empty_batch")

    settings = get_settings()
    if len(images) > settings.max_batch_image_count:
        raise HTTPException(
            status_code=400,
            detail=f"Batch image count exceeds maximum allowed limit of {settings.max_batch_image_count}",
        )

    frames: list[CanonicalInspectionFrame] = []
    sorted_images = sorted(images, key=lambda f: f.filename or "")

    for idx, img in enumerate(sorted_images):
        img_bytes = await img.read()
        dist = (
            (distance_start_m or 0.0) + (idx * distance_step_m)
            if distance_step_m is not None
            else None
        )
        frames.append(
            CanonicalInspectionFrame(
                mission_id=mission_id,
                robot_id=robot_id,
                camera_id=camera_id,
                source=source,
                frame_index=idx,
                image_bytes=img_bytes,
                distance_m=dist,
            )
        )

    try:
        batch_res = ingestion_gateway.ingest_batch(db, frames)
        return batch_res.to_dict()
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Batch ingestion failed: {exc}"
        ) from exc


@router.post("/ingest/directory", status_code=201)
def ingest_directory_images(
    payload: DirectoryIngestionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Offline workflow endpoint: Ingest all photos in a server-accessible directory."""
    target_path = Path(payload.directory_path).resolve()
    ALLOWED_INGEST_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        target_path.relative_to(ALLOWED_INGEST_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Directory path must be within allowed import root ({ALLOWED_INGEST_ROOT})",
        ) from exc

    try:
        batch_res = ingestion_gateway.ingest_photo_directory(
            db,
            directory_path=payload.directory_path,
            mission_id=payload.mission_id,
            distance_start_m=payload.distance_start_m,
            distance_step_m=payload.distance_step_m,
            robot_id=payload.robot_id,
            camera_id=payload.camera_id,
            auto_create_mission=payload.auto_create_mission,
        )
        return batch_res.to_dict()
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidImageContentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Directory ingestion failed: {exc}"
        ) from exc


@router.post("/ingest/video", status_code=201)
def ingest_video_file_endpoint(
    payload: VideoIngestionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Offline workflow endpoint: Process an offline video file into PipeVision."""
    target_path = Path(payload.video_path).resolve()
    ALLOWED_INGEST_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        target_path.relative_to(ALLOWED_INGEST_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Video file path must be within allowed import root ({ALLOWED_INGEST_ROOT})",
        ) from exc

    try:
        video_res = ingestion_gateway.ingest_video_file(
            db,
            video_path=payload.video_path,
            mission_id=payload.mission_id,
            frame_interval=payload.frame_interval,
            target_fps=payload.target_fps,
            max_frames=payload.max_frames,
            start_timestamp=payload.start_timestamp,
            distance_start_m=payload.distance_start_m,
            distance_step_m=payload.distance_step_m,
            robot_id=payload.robot_id,
            camera_id=payload.camera_id,
            auto_create_mission=payload.auto_create_mission,
        )
        return video_res.to_dict()
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidImageContentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UnsupportedImageTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Video ingestion failed: {exc}"
        ) from exc


# ============================================================================
# HARDWARE CAPTURE WORKER ENDPOINTS
# ============================================================================


class HardwareCaptureStartRequest(BaseModel):
    fps: float = Field(default=2.0, ge=0.5, le=10.0)
    camera_id: str = Field(default="cam-01", min_length=1, max_length=64)


class HardwareCaptureStatusResponse(BaseModel):
    mission_id: str
    camera_id: str
    camera_connected: bool
    is_ingesting: bool
    fps: float
    frame_count: int
    last_frame_timestamp: str | None = None
    inference_available: bool
    last_error: str | None = None


@router.post("/missions/{mission_id}/capture/start", status_code=200)
def start_hardware_capture(
    mission_id: str,
    payload: HardwareCaptureStartRequest | None = None,
) -> HardwareCaptureStatusResponse:
    """Start background frame ingestion from ESP32-CAM snapshot endpoint into Sewer-ML perception pipeline."""
    fps = payload.fps if payload else 2.0
    camera_id = payload.camera_id if payload else "cam-01"
    status = hardware_ingestion_manager.start_worker(mission_id, camera_id=camera_id, fps=fps)
    return HardwareCaptureStatusResponse(**status.to_dict())


@router.post("/missions/{mission_id}/capture/stop")
async def stop_hardware_capture(
    mission_id: str,
    camera_id: str = Query(default="cam-01"),
) -> HardwareCaptureStatusResponse:
    """Stop background frame ingestion worker for a mission."""
    status = await hardware_ingestion_manager.stop_worker(mission_id, camera_id=camera_id)
    return HardwareCaptureStatusResponse(**status.to_dict())


@router.get("/missions/{mission_id}/capture/status")
def get_hardware_capture_status(
    mission_id: str,
    camera_id: str = Query(default="cam-01"),
) -> HardwareCaptureStatusResponse:
    """Query health, frame count, connection, and inference status of hardware ingestion worker."""
    status = hardware_ingestion_manager.get_status(mission_id, camera_id=camera_id)
    return HardwareCaptureStatusResponse(**status.to_dict())
