from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class VideoFrame:
    frame_index: int
    timestamp_s: float
    frame: np.ndarray


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
