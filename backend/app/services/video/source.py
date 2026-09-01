from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VideoFrame:
    frame_index: int
    timestamp_s: float
    frame: np.ndarray


class CameraSource(Protocol):
    """Backend camera source contract independent of a specific device."""

    def mjpeg_chunks(self) -> Iterator[bytes]: ...
    def close(self) -> None: ...


class ESP32CAMSource:
    """Proxy a configurable ESP32-CAM HTTP/MJPEG stream over the local network.

    The firmware endpoint is intentionally not assumed. ``url`` must be
    supplied by deployment configuration and is opened only when streaming.
    """

    def __init__(self, url: str, timeout_s: float = 3.0) -> None:
        if not url or not url.strip():
            raise ValueError("ESP32-CAM stream URL must be configured.")
        if not url.startswith(("http://", "https://")):
            raise ValueError("ESP32-CAM stream URL must use http:// or https://.")
        if timeout_s <= 0:
            raise ValueError("ESP32-CAM timeout must be positive.")
        self.url = url
        self.timeout_s = timeout_s
        self._response = None

    def mjpeg_chunks(self) -> Iterator[bytes]:
        request = Request(self.url, headers={"Accept": "multipart/x-mixed-replace, image/jpeg"})
        try:
            self._response = urlopen(request, timeout=self.timeout_s)
            while True:
                chunk = self._response.read(8192)
                if not chunk:
                    break
                yield chunk
        except (OSError, URLError) as exc:
            logger.warning("ESP32-CAM stream unavailable at %s: %s", self.url, exc)
        finally:
            self.close()

    def close(self) -> None:
        if self._response is not None:
            self._response.close()
            self._response = None


class VideoSource:
    def __init__(self, source: str | int):
        if isinstance(source, str) and source.isdigit():
            source = int(source)

        self.source = source
        self.capture = cv2.VideoCapture(source)

        if not self.capture.isOpened():
            raise RuntimeError(f"Unable to open video source: {self.source}")

    @property
    def fps(self) -> float:
        value = self.capture.get(cv2.CAP_PROP_FPS)
        return value if value > 0 else 30.0

    @property
    def width(self) -> int:
        return int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        return int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def frames(self) -> Iterator[VideoFrame]:
        index = 0

        while True:
            ok, frame = self.capture.read()

            if not ok:
                break

            yield VideoFrame(
                frame_index=index,
                timestamp_s=index / self.fps,
                frame=frame,
            )

            index += 1

    def close(self) -> None:
        self.capture.release()
