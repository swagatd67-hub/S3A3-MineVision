from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.services.video.detection import (
    NullDetector,
    analyze_image,
    load_detector,
    result_to_dict,
)
from backend.app.services.video.frame_store import (
    FrameMetadata,
    FrameMetadataStore,
)

router = APIRouter(prefix="/video", tags=["video"])

frame_store = FrameMetadataStore()
pipeline_detector = NullDetector()


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
            "timestamp": metadata.timestamp.isoformat(),
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
            "timestamp": metadata.timestamp.isoformat(),
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
                "timestamp": item.timestamp.isoformat(),
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
        "timestamp": record.timestamp.isoformat(),
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
        "timestamp": record.timestamp.isoformat(),
        "distance_m": record.distance_m,
        "source": record.source,
        **result_to_dict(result),
    }
