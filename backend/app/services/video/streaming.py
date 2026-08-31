from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import AsyncGenerator

import cv2
import numpy as np
from PIL import Image, ImageDraw

from backend.app.services.video.frame_store import FrameMetadataStore

logger = logging.getLogger(__name__)


def generate_placeholder_jpeg(
    text: str = "NO FEED", width: int = 640, height: int = 480
) -> bytes:
    """Generate a deterministic synthetic placeholder JPEG frame when live frames are pending or missing."""
    try:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        # Draw background grid lines
        for y in range(0, height, 40):
            cv2.line(img, (0, y), (width, y), (20, 40, 40), 1)
        for x in range(0, width, 40):
            cv2.line(img, (x, 0), (x, height), (20, 40, 40), 1)

        cv2.putText(
            img, text, (30, height // 2 - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (93, 230, 255), 2
        )
        cv2.putText(
            img,
            "DEV STREAM • SIMULATION / PLAYBACK",
            (30, height // 2 + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (100, 156, 150),
            1,
        )
        _, buffer = cv2.imencode(".jpg", img)
        return buffer.tobytes()
    except Exception:  # noqa: BLE001
        # Pure PIL fallback if OpenCV fails for any reason
        pil_img = Image.new("RGB", (width, height), color=(10, 22, 23))
        draw = ImageDraw.Draw(pil_img)
        draw.text((30, height // 2), text, fill=(93, 230, 255))
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG")
        return buf.getvalue()


async def mjpeg_frame_generator(
    mission_id: str,
    frame_store: FrameMetadataStore,
    camera_id: str = "cam-01",
    fps: float = 10.0,
    loop: bool = True,
) -> AsyncGenerator[bytes, None]:
    """Asynchronous frame generator yielding MJPEG multipart boundaries for FastAPI StreamingResponse.

    Gracefully streams stored frames for the specified mission, or falls back to synthetic
    development/placeholder frames if no hardware frame source is connected. Cleanly exits on client disconnect.
    """
    safe_fps = min(max(fps, 1.0), 60.0)
    delay = 1.0 / safe_fps
    idx = 0

    try:
        while True:
            records = frame_store.list(mission_id, limit=10000)
            jpeg_bytes: bytes | None = None

            if records:
                if idx >= len(records):
                    if not loop:
                        break
                    idx = 0

                record = records[idx]
                image_path = frame_store.image_path(mission_id, record.frame_index)
                if image_path and image_path.exists():
                    try:
                        jpeg_bytes = image_path.read_bytes()
                    except (OSError, ValueError):
                        jpeg_bytes = None
                idx += 1
            elif not loop:
                jpeg_bytes = generate_placeholder_jpeg(
                    f"MISSION: {mission_id} [{camera_id}]"
                )
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
                break

            if not jpeg_bytes:
                jpeg_bytes = generate_placeholder_jpeg(
                    f"MISSION: {mission_id} [{camera_id}]"
                )

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
            )
            await asyncio.sleep(delay)
    except (asyncio.CancelledError, GeneratorExit):
        # Client disconnect or streaming task cancellation - clean exit
        logger.debug("MJPEG stream connection closed for mission '%s'", mission_id)
