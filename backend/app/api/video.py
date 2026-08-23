import math
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
from backend.app.services.video.sewer_classifier import (
    get_sewer_classifier_engine,
)
from robot.localization.models import LocalizationQuality, RobotPose

router = APIRouter(prefix="/video", tags=["video"])

frame_store = FrameMetadataStore()
pipeline_detector = NullDetector()
ingestion_gateway = InspectionIngestionGateway()


class FrameMetadataRequest(BaseModel):
    mission_id: str = Field(min_length=1, max_length=64)
    frame_index: int = Field(ge=0)
    timestamp: datetime
    distance_m: float
    source: str = Field(min_length=1, max_length=128)
    frame_path: str | None = Field(default=None, max_length=512)


@router.get("/health")
def video_health() -> dict:
    return {
        "service": "video",
        "status": "ready",
        "supported_sources": ["file", "webcam"],
        "image_storage": True,
        "detection_pipeline": True,
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
            "timestamp": metadata.timestamp.isoformat() if metadata.timestamp is not None else None,
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
            "timestamp": metadata.timestamp.isoformat() if metadata.timestamp is not None else None,
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
                "timestamp": item.timestamp.isoformat() if item.timestamp is not None else None,
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
        "timestamp": record.timestamp.isoformat() if record.timestamp is not None else None,
        "distance_m": record.distance_m,
        "source": record.source,
        "frame_path": record.frame_path,
    }


@router.get("/missions/{mission_id}/frames/{frame_index}/image")
def get_frame_image(
    mission_id: str,
    frame_index: int,
):
    path = frame_store.image_path(
        mission_id,
        frame_index,
    )

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

    image_path = frame_store.image_path(
        mission_id,
        frame_index,
    )

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
        "timestamp": record.timestamp.isoformat() if record.timestamp is not None else None,
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

    image_path = frame_store.image_path(
        mission_id,
        frame_index,
    )

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
        "timestamp": record.timestamp.isoformat() if record.timestamp is not None else None,
        "distance_m": record.distance_m,
        "source": record.source,
        **result.to_dict(),
    }


class DirectoryIngestionRequest(BaseModel):
    mission_id: str = Field(min_length=1, max_length=64)
    directory_path: str = Field(min_length=1, max_length=512)
    distance_step_m: float | None = Field(default=None, ge=0.0)
    robot_id: str | None = Field(default=None, max_length=64)
    camera_id: str | None = Field(default=None, max_length=64)


ALLOWED_INGEST_ROOT = Path("data/import").resolve()


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

    # Construct pose if spatial coordinates are explicitly provided.
    # Per RobotPose specification (robot/localization/models.py), x is the canonical longitudinal
    # pipe coordinate (x = distance_m).
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
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc


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

    frames: list[CanonicalInspectionFrame] = []

    # Sort images deterministically by filename
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
        raise HTTPException(status_code=500, detail=f"Batch ingestion failed: {exc}") from exc


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
            distance_step_m=payload.distance_step_m,
            robot_id=payload.robot_id,
            camera_id=payload.camera_id,
        )
        return batch_res.to_dict()
    except MissionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidImageContentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Directory ingestion failed: {exc}") from exc
