from fastapi import APIRouter

router = APIRouter(prefix="/video", tags=["video"])


@router.get("/health")
def video_health() -> dict:
    return {
        "service": "video",
        "status": "ready",
        "supported_sources": ["file", "webcam"],
    }