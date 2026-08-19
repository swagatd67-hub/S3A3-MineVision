from dataclasses import dataclass


@dataclass(frozen=True)
class VideoMetadata:
    source: str
    fps: float
    width: int
    height: int
