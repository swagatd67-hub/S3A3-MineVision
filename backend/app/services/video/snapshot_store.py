from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from backend.app.config import get_settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SnapshotRecord:
    snapshot_id: str
    mission_id: str
    frame_index: int
    timestamp: datetime | None = None
    distance_m: float | None = None
    camera_id: str | None = None
    frame_path: str | None = None
    image_url: str | None = None
    notes: str | None = None
    created_at: datetime | None = None


class SnapshotStore:
    """Persist media snapshots backed by existing media/frame storage architecture."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            self.root = get_settings().media_storage_root.resolve()
        else:
            self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    @staticmethod
    def _safe_id(value: str) -> str:
        value = value.strip()
        safe = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_" for char in value
        )
        return safe.strip("_") or "unknown"

    def _snapshots_path(self, mission_id: str) -> Path:
        return self.root / f"{self._safe_id(mission_id)}_snapshots.jsonl"

    def create(self, snapshot: SnapshotRecord) -> SnapshotRecord:
        created_ts = snapshot.created_at or utc_now()
        payload: dict[str, Any] = {
            "snapshot_id": snapshot.snapshot_id,
            "mission_id": snapshot.mission_id,
            "frame_index": snapshot.frame_index,
            "timestamp": (
                snapshot.timestamp.isoformat()
                if snapshot.timestamp is not None
                else None
            ),
            "distance_m": snapshot.distance_m,
            "camera_id": snapshot.camera_id,
            "frame_path": snapshot.frame_path,
            "image_url": snapshot.image_url,
            "notes": snapshot.notes,
            "created_at": created_ts.isoformat(),
        }

        with (
            self._lock,
            self._snapshots_path(snapshot.mission_id).open(
                "a", encoding="utf-8"
            ) as handle,
        ):
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

        return SnapshotRecord(
            snapshot_id=snapshot.snapshot_id,
            mission_id=snapshot.mission_id,
            frame_index=snapshot.frame_index,
            timestamp=snapshot.timestamp,
            distance_m=snapshot.distance_m,
            camera_id=snapshot.camera_id,
            frame_path=snapshot.frame_path,
            image_url=snapshot.image_url,
            notes=snapshot.notes,
            created_at=created_ts,
        )

    def list(self, mission_id: str, limit: int = 1000) -> list[SnapshotRecord]:
        path = self._snapshots_path(mission_id)
        if not path.exists():
            return []

        records: list[SnapshotRecord] = []
        with self._lock, path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                raw_ts = payload.get("timestamp")
                ts = datetime.fromisoformat(raw_ts) if raw_ts is not None else None
                raw_created = payload.get("created_at")
                created = (
                    datetime.fromisoformat(raw_created)
                    if raw_created is not None
                    else None
                )
                raw_dist = payload.get("distance_m")
                dist = float(raw_dist) if raw_dist is not None else None

                records.append(
                    SnapshotRecord(
                        snapshot_id=str(payload["snapshot_id"]),
                        mission_id=str(payload["mission_id"]),
                        frame_index=int(payload["frame_index"]),
                        timestamp=ts,
                        distance_m=dist,
                        camera_id=(
                            str(payload["camera_id"])
                            if payload.get("camera_id") is not None
                            else None
                        ),
                        frame_path=(
                            str(payload["frame_path"])
                            if payload.get("frame_path") is not None
                            else None
                        ),
                        image_url=(
                            str(payload["image_url"])
                            if payload.get("image_url") is not None
                            else None
                        ),
                        notes=(
                            str(payload["notes"])
                            if payload.get("notes") is not None
                            else None
                        ),
                        created_at=created,
                    )
                )

        return records[-max(1, limit) :]

    def get(self, mission_id: str, snapshot_id: str) -> SnapshotRecord | None:
        for item in self.list(mission_id, limit=100000):
            if item.snapshot_id == snapshot_id:
                return item
        return None

    def delete(self, mission_id: str, snapshot_id: str) -> bool:
        path = self._snapshots_path(mission_id)
        if not path.exists():
            return False

        records = self.list(mission_id, limit=100000)
        filtered = [r for r in records if r.snapshot_id != snapshot_id]
        if len(filtered) == len(records):
            return False

        with self._lock, path.open("w", encoding="utf-8") as handle:
            for r in filtered:
                payload = {
                    "snapshot_id": r.snapshot_id,
                    "mission_id": r.mission_id,
                    "frame_index": r.frame_index,
                    "timestamp": (
                        r.timestamp.isoformat()
                        if r.timestamp is not None
                        else None
                    ),
                    "distance_m": r.distance_m,
                    "camera_id": r.camera_id,
                    "frame_path": r.frame_path,
                    "image_url": r.image_url,
                    "notes": r.notes,
                    "created_at": (
                        r.created_at.isoformat()
                        if r.created_at is not None
                        else None
                    ),
                }
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        return True
