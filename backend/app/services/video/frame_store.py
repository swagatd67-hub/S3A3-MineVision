from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Iterable


@dataclass(frozen=True)
class FrameMetadata:
    mission_id: str
    frame_index: int
    timestamp: datetime
    distance_m: float
    source: str
    frame_path: str | None = None


class FrameMetadataStore:
    """Small JSONL-backed store for synchronized inspection-frame metadata.

    JSONL is intentionally used in the prototype phase so Day 4 does not require
    another database migration. The storage contract is kept independent of the
    API and can later move to PostgreSQL without changing the frame schema.
    """

    def __init__(self, root: str | Path = "video/storage") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _path(self, mission_id: str) -> Path:
        safe_id = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in mission_id
        )
        return self.root / f"{safe_id}.jsonl"

    def append(self, metadata: FrameMetadata) -> FrameMetadata:
        payload = asdict(metadata)
        payload["timestamp"] = metadata.timestamp.isoformat()

        with self._lock:
            with self._path(metadata.mission_id).open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

        return metadata

    def list(
        self,
        mission_id: str,
        *,
        limit: int = 1000,
    ) -> list[FrameMetadata]:
        path = self._path(mission_id)

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
                        mission_id=payload["mission_id"],
                        frame_index=int(payload["frame_index"]),
                        timestamp=datetime.fromisoformat(payload["timestamp"]),
                        distance_m=float(payload["distance_m"]),
                        source=payload["source"],
                        frame_path=payload.get("frame_path"),
                    )
                )

        return records[-max(1, limit):]

    def get(self, mission_id: str, frame_index: int) -> FrameMetadata | None:
        for item in self.list(mission_id, limit=100000):
            if item.frame_index == frame_index:
                return item
        return None
