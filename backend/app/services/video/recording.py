from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from backend.app.config import get_settings
from backend.app.services.video.frame_store import FrameMetadataStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RecordingSession:
    recording_id: str
    mission_id: str
    camera_id: str | None
    start_time: datetime
    stop_time: datetime | None = None
    status: str = "RECORDING"  # RECORDING, STOPPED, COMPLETED, FAILED
    frame_count: int = 0
    media_location: str | None = None
    created_at: datetime = field(default_factory=utc_now)


class RecordingManager:
    """Manage video/media recording sessions for missions."""

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

    def _recordings_path(self, mission_id: str) -> Path:
        return self.root / f"{self._safe_id(mission_id)}_recordings.jsonl"

    def start_recording(
        self, mission_id: str, camera_id: str | None = None
    ) -> RecordingSession:
        active = self.get_active_recording(mission_id)
        if active is not None:
            raise ValueError("recording_already_active")

        recording_id = f"rec-{uuid.uuid4().hex[:12]}"
        now = utc_now()
        session = RecordingSession(
            recording_id=recording_id,
            mission_id=mission_id,
            camera_id=camera_id,
            start_time=now,
            status="RECORDING",
            created_at=now,
        )

        payload: dict[str, Any] = {
            "recording_id": session.recording_id,
            "mission_id": session.mission_id,
            "camera_id": session.camera_id,
            "start_time": session.start_time.isoformat(),
            "stop_time": None,
            "status": session.status,
            "frame_count": session.frame_count,
            "media_location": session.media_location,
            "created_at": session.created_at.isoformat(),
        }

        with (
            self._lock,
            self._recordings_path(mission_id).open("a", encoding="utf-8") as handle,
        ):
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

        return session

    def stop_recording(
        self,
        mission_id: str,
        recording_id: str | None = None,
        frame_store: FrameMetadataStore | None = None,
    ) -> RecordingSession:
        sessions = self.list_recordings(mission_id, limit=100000)
        target: RecordingSession | None = None

        for s in reversed(sessions):
            if recording_id:
                if s.recording_id == recording_id:
                    target = s
                    break
            elif s.status == "RECORDING":
                target = s
                break

        if target is None or target.status != "RECORDING":
            raise ValueError("no_active_recording_found")

        now = utc_now()
        frames_count = target.frame_count
        media_loc = target.media_location

        if frame_store is not None:
            frames = frame_store.list(mission_id, limit=100000)
            frames_count = len(frames)
            media_path = frame_store.root / frame_store._safe_id(mission_id)
            try:
                media_loc = media_path.relative_to(Path.cwd()).as_posix()
            except ValueError:
                media_loc = media_path.as_posix()

        stopped_session = RecordingSession(
            recording_id=target.recording_id,
            mission_id=target.mission_id,
            camera_id=target.camera_id,
            start_time=target.start_time,
            stop_time=now,
            status="STOPPED",
            frame_count=frames_count,
            media_location=media_loc,
            created_at=target.created_at,
        )

        updated_list = [
            stopped_session if s.recording_id == target.recording_id else s
            for s in sessions
        ]

        with self._lock, self._recordings_path(mission_id).open(
            "w", encoding="utf-8"
        ) as handle:
            for s in updated_list:
                payload = {
                    "recording_id": s.recording_id,
                    "mission_id": s.mission_id,
                    "camera_id": s.camera_id,
                    "start_time": s.start_time.isoformat(),
                    "stop_time": (
                        s.stop_time.isoformat()
                        if s.stop_time is not None
                        else None
                    ),
                    "status": s.status,
                    "frame_count": s.frame_count,
                    "media_location": s.media_location,
                    "created_at": s.created_at.isoformat(),
                }
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

        return stopped_session

    def list_recordings(
        self, mission_id: str, limit: int = 1000
    ) -> list[RecordingSession]:
        path = self._recordings_path(mission_id)
        if not path.exists():
            return []

        records: list[RecordingSession] = []
        with self._lock, path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                raw_start = payload.get("start_time")
                start_ts = (
                    datetime.fromisoformat(raw_start)
                    if raw_start is not None
                    else utc_now()
                )
                raw_stop = payload.get("stop_time")
                stop_ts = (
                    datetime.fromisoformat(raw_stop)
                    if raw_stop is not None
                    else None
                )
                raw_created = payload.get("created_at")
                created_ts = (
                    datetime.fromisoformat(raw_created)
                    if raw_created is not None
                    else start_ts
                )

                records.append(
                    RecordingSession(
                        recording_id=str(payload["recording_id"]),
                        mission_id=str(payload["mission_id"]),
                        camera_id=(
                            str(payload["camera_id"])
                            if payload.get("camera_id") is not None
                            else None
                        ),
                        start_time=start_ts,
                        stop_time=stop_ts,
                        status=str(payload.get("status", "RECORDING")),
                        frame_count=int(payload.get("frame_count", 0)),
                        media_location=(
                            str(payload["media_location"])
                            if payload.get("media_location") is not None
                            else None
                        ),
                        created_at=created_ts,
                    )
                )

        return records[-max(1, limit) :]

    def get_active_recording(self, mission_id: str) -> RecordingSession | None:
        for s in reversed(self.list_recordings(mission_id, limit=100000)):
            if s.status == "RECORDING":
                return s
        return None

    def get_status(self, mission_id: str) -> RecordingSession | None:
        sessions = self.list_recordings(mission_id, limit=100000)
        if not sessions:
            return None
        active = self.get_active_recording(mission_id)
        return active if active is not None else sessions[-1]

    def get_recording(
        self, mission_id: str, recording_id: str
    ) -> RecordingSession | None:
        for s in self.list_recordings(mission_id, limit=100000):
            if s.recording_id == recording_id:
                return s
        return None
