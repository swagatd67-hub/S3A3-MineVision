from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock


@dataclass(frozen=True)
class FrameMetadata:
    mission_id: str
    frame_index: int
    timestamp: datetime
    distance_m: float
    source: str
    frame_path: str | None = None


class FrameMetadataStore:
    """Persist synchronized frame metadata and image files for a mission."""

    def __init__(self, root: str | Path = "video/storage") -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    @staticmethod
    def _safe_id(value: str) -> str:
        value = value.strip()

        safe = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in value
        )

        return safe.strip("_") or "unknown"

    def _mission_dir(self, mission_id: str) -> Path:
        return self.root / self._safe_id(mission_id)

    def _metadata_path(self, mission_id: str) -> Path:
        return self.root / f"{self._safe_id(mission_id)}.jsonl"

    def _frame_path(
        self,
        mission_id: str,
        frame_index: int,
        extension: str = ".jpg",
    ) -> Path:
        if not extension.startswith("."):
            extension = f".{extension}"

        safe_ext = extension.lower()

        if safe_ext not in {".jpg", ".jpeg", ".png"}:
            raise ValueError("unsupported image extension")

        return (
            self._mission_dir(mission_id)
            / f"frame-{frame_index:06d}{safe_ext}"
        )

    def save_image(
        self,
        *,
        mission_id: str,
        frame_index: int,
        image_bytes: bytes,
        extension: str = ".jpg",
    ) -> str:
        if not image_bytes:
            raise ValueError("image_bytes cannot be empty")

        path = self._frame_path(
            mission_id,
            frame_index,
            extension,
        )

        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            path.write_bytes(image_bytes)

        try:
            return path.relative_to(Path.cwd()).as_posix()
        except ValueError:
            return path.as_posix()

    def append(self, metadata: FrameMetadata) -> FrameMetadata:
        payload: dict[str, object] = {
            "mission_id": metadata.mission_id,
            "frame_index": metadata.frame_index,
            "timestamp": metadata.timestamp.isoformat(),
            "distance_m": metadata.distance_m,
            "source": metadata.source,
            "frame_path": metadata.frame_path,
        }

        with self._lock:
            with self._metadata_path(metadata.mission_id).open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(
                    json.dumps(
                        payload,
                        separators=(",", ":"),
                    )
                    + "\n"
                )

        return metadata

    def list(
        self,
        mission_id: str,
        *,
        limit: int = 1000,
    ) -> list[FrameMetadata]:
        path = self._metadata_path(mission_id)

        if not path.exists():
            return []

        records: list[FrameMetadata] = []

        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue

                payload = json.loads(line)

                records.append(
                    FrameMetadata(
                        mission_id=str(payload["mission_id"]),
                        frame_index=int(payload["frame_index"]),
                        timestamp=datetime.fromisoformat(
                            str(payload["timestamp"])
                        ),
                        distance_m=float(payload["distance_m"]),
                        source=str(payload["source"]),
                        frame_path=(
                            str(payload["frame_path"])
                            if payload.get("frame_path") is not None
                            else None
                        ),
                    )
                )

        return records[-max(1, limit):]

    def get(
        self,
        mission_id: str,
        frame_index: int,
    ) -> FrameMetadata | None:
        for item in self.list(
            mission_id,
            limit=100000,
        ):
            if item.frame_index == frame_index:
                return item

        return None

    def image_path(
        self,
        mission_id: str,
        frame_index: int,
    ) -> Path | None:
        record = self.get(
            mission_id,
            frame_index,
        )

        if record is None or not record.frame_path:
            return None

        path = Path(record.frame_path)

        if not path.is_absolute():
            path = Path.cwd() / path

        path = path.resolve()

        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(
                "frame path escapes storage root"
            ) from exc

        return path