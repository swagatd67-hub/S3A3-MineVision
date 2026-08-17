from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.video.frame_store import (
    FrameMetadata,
    FrameMetadataStore,
)

router = APIRouter(prefix="/video", tags=["video"])

frame_store = FrameMetadataStore()


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
        raise HTTPException(status_code=404, detail="frame_not_found")

    return {
        "mission_id": record.mission_id,
        "frame_index": record.frame_index,
        "timestamp": record.timestamp.isoformat(),
        "distance_m": record.distance_m,
        "source": record.source,
        "frame_path": record.frame_path,
    }
