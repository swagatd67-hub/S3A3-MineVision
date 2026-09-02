"""ESP32-CAM Hardware Frame Ingestion Service.

Provides background worker orchestration to continuously fetch frames from the ESP32-CAM
snapshot endpoint (/capture) at a controlled FPS and pass them into PipeVision's existing
InspectionIngestionGateway pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.app.config import get_settings
from backend.app.db import SessionLocal
from backend.app.services.inspection.gateway import (
    InspectionIngestionGateway,
    _ensure_mission_exists,
)
from backend.app.services.inspection.models import CanonicalInspectionFrame
from backend.app.services.video.sewer_classifier import (
    get_default_checkpoint_path,
    get_sewer_classifier_engine,
)
from backend.app.services.video.source import ESP32CAMSource

logger = logging.getLogger(__name__)


@dataclass
class IngestionWorkerStatus:
    """Status snapshot of an ESP32-CAM frame ingestion worker."""

    mission_id: str
    camera_id: str
    is_ingesting: bool
    camera_connected: bool
    fps: float
    frame_count: int
    last_frame_timestamp: str | None
    inference_available: bool
    last_error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "camera_id": self.camera_id,
            "is_ingesting": self.is_ingesting,
            "camera_connected": self.camera_connected,
            "fps": round(self.fps, 2),
            "frame_count": self.frame_count,
            "last_frame_timestamp": self.last_frame_timestamp,
            "inference_available": self.inference_available,
            "last_error": self.last_error,
        }


class HardwareIngestionManager:
    """Registry and lifecycle manager for background ESP32-CAM frame ingestion workers."""

    _instance: HardwareIngestionManager | None = None

    def __init__(self) -> None:
        self._workers: dict[str, dict[str, Any]] = {}
        self._gateway = InspectionIngestionGateway()

    @classmethod
    def get_instance(cls) -> HardwareIngestionManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for testing."""
        if cls._instance is not None:
            for worker in list(cls._instance._workers.values()):
                if worker.get("is_ingesting") and worker.get("stop_event"):
                    worker["stop_event"].set()
            cls._instance._workers.clear()
            cls._instance = None

    def get_status(self, mission_id: str, camera_id: str = "cam-01") -> IngestionWorkerStatus:
        key = f"{mission_id}:{camera_id}"
        worker = self._workers.get(key)
        checkpoint_exists = get_default_checkpoint_path().exists()

        if worker is None:
            return IngestionWorkerStatus(
                mission_id=mission_id,
                camera_id=camera_id,
                is_ingesting=False,
                camera_connected=False,
                fps=0.0,
                frame_count=0,
                last_frame_timestamp=None,
                inference_available=checkpoint_exists,
                last_error=None,
            )

        last_ts = worker["last_frame_timestamp"]
        return IngestionWorkerStatus(
            mission_id=mission_id,
            camera_id=camera_id,
            is_ingesting=worker["is_ingesting"],
            camera_connected=worker["camera_connected"],
            fps=worker["fps"],
            frame_count=worker["frame_count"],
            last_frame_timestamp=last_ts.isoformat() if isinstance(last_ts, datetime) else last_ts,
            inference_available=worker["inference_available"],
            last_error=worker["last_error"],
        )

    def start_worker(
        self,
        mission_id: str,
        camera_id: str = "cam-01",
        fps: float = 2.0,
    ) -> IngestionWorkerStatus:
        key = f"{mission_id}:{camera_id}"
        existing = self._workers.get(key)
        if existing and existing["is_ingesting"]:
            logger.info("Ingestion worker already active for mission '%s' camera '%s'", mission_id, camera_id)
            return self.get_status(mission_id, camera_id)

        safe_fps = min(max(fps, 0.5), 10.0)
        stop_event = asyncio.Event()
        checkpoint_exists = get_default_checkpoint_path().exists()

        worker_data: dict[str, Any] = {
            "mission_id": mission_id,
            "camera_id": camera_id,
            "is_ingesting": True,
            "camera_connected": False,
            "fps": safe_fps,
            "frame_count": 0,
            "last_frame_timestamp": None,
            "inference_available": checkpoint_exists,
            "last_error": None,
            "stop_event": stop_event,
            "task": None,
        }

        self._workers[key] = worker_data

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                self._run_worker_loop(key, mission_id, camera_id, safe_fps, stop_event)
            )
            worker_data["task"] = task
        except RuntimeError:
            logger.warning("No running asyncio event loop found when starting worker for '%s'", key)

        logger.info("Started ESP32-CAM hardware ingestion worker for mission '%s' at %.1f FPS", mission_id, safe_fps)
        return self.get_status(mission_id, camera_id)

    async def stop_worker(self, mission_id: str, camera_id: str = "cam-01") -> IngestionWorkerStatus:
        key = f"{mission_id}:{camera_id}"
        worker = self._workers.get(key)
        if worker is None or not worker["is_ingesting"]:
            return self.get_status(mission_id, camera_id)

        worker["stop_event"].set()
        task: asyncio.Task | None = worker.get("task")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception) as exc:  # noqa: BLE001
                logger.debug("Task cancellation exception handled: %s", exc)

        worker["is_ingesting"] = False
        logger.info("Stopped ESP32-CAM hardware ingestion worker for mission '%s'", mission_id)
        return self.get_status(mission_id, camera_id)

    @staticmethod
    def _do_ingest_frame(
        gateway: InspectionIngestionGateway,
        mission_id: str,
        frame: CanonicalInspectionFrame,
        sewer_engine: Any,
    ) -> None:
        with SessionLocal() as db:
            _ensure_mission_exists(db, mission_id)
            gateway.ingest_frame(
                db=db,
                frame=frame,
                sewer_engine=sewer_engine,
                commit=True,
            )

    async def _run_worker_loop(
        self,
        key: str,
        mission_id: str,
        camera_id: str,
        fps: float,
        stop_event: asyncio.Event,
    ) -> None:
        settings = get_settings()
        source: ESP32CAMSource | None = None
        if settings.camera_source_type == "esp32cam":
            try:
                source = ESP32CAMSource(
                    url=settings.esp32_cam_url or "",
                    snapshot_url=settings.esp32_cam_snapshot_url,
                    timeout_s=settings.esp32_cam_timeout_s,
                )
            except ValueError as exc:
                logger.warning("Failed to initialize ESP32CAMSource for worker: %s", exc)

        sewer_engine = get_sewer_classifier_engine(allow_null_fallback=True)
        delay = 1.0 / fps

        try:
            while not stop_event.is_set():
                worker = self._workers.get(key)
                if not worker or not worker["is_ingesting"]:
                    break

                snapshot_bytes: bytes | None = None
                if source is not None:
                    snapshot_bytes = await asyncio.to_thread(source.fetch_snapshot)
                else:
                    # In simulator mode, generate a placeholder JPEG frame for pipeline testing
                    from backend.app.services.video.streaming import (
                        generate_placeholder_jpeg,
                    )
                    snapshot_bytes = generate_placeholder_jpeg(f"SIMULATOR [{mission_id}]")

                if not snapshot_bytes:
                    worker["camera_connected"] = False
                    worker["last_error"] = "Snapshot fetch returned no bytes or timed out"
                    await asyncio.sleep(delay)
                    continue

                worker["camera_connected"] = True
                frame_idx = worker["frame_count"] + 1

                canonical_frame = CanonicalInspectionFrame(
                    mission_id=mission_id,
                    camera_id=camera_id,
                    source="live",
                    frame_index=frame_idx,
                    image_bytes=snapshot_bytes,
                    timestamp=datetime.now(timezone.utc),
                )

                try:
                    await asyncio.to_thread(
                        self._do_ingest_frame,
                        self._gateway,
                        mission_id,
                        canonical_frame,
                        sewer_engine,
                    )

                    worker["frame_count"] = frame_idx
                    worker["last_frame_timestamp"] = datetime.now(timezone.utc)
                    worker["last_error"] = None

                except Exception as exc:  # noqa: BLE001
                    logger.warning("Error ingesting frame %d for mission '%s': %s", frame_idx, mission_id, exc)
                    worker["last_error"] = str(exc)

                await asyncio.sleep(delay)

        except asyncio.CancelledError:
            logger.debug("Ingestion worker loop cancelled for key '%s'", key)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("Unhandled error in ingestion worker loop for key '%s': %s", key, exc)
            worker = self._workers.get(key)
            if worker:
                worker["last_error"] = str(exc)
        finally:
            worker = self._workers.get(key)
            if worker:
                worker["is_ingesting"] = False
