"""Generic Local Software-Generated Gas Sensor Service.

Provides smooth, bounded gas index generation (0-100) and broadcasts updates
via PipeVision's existing telemetry WebSocket architecture.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any

from backend.app.config import get_settings
from backend.app.realtime import telemetry_broadcaster

logger = logging.getLogger(__name__)


def classify_gas_status(value: float) -> str:
    """Classify unitless gas index (0-100) into application status levels."""
    if value < 40.0:
        return "NORMAL"
    elif value < 70.0:
        return "ELEVATED"
    elif value < 90.0:
        return "HIGH"
    else:
        return "CRITICAL"


class GasSensorGenerator:
    """Deterministic smooth variation generator with bounded noise for unitless gas index."""

    def __init__(
        self,
        min_val: float = 0.0,
        max_val: float = 100.0,
        initial_val: float = 25.0,
        target_center: float = 35.0,
    ) -> None:
        self.min_val = min_val
        self.max_val = max_val
        self._current_val = initial_val
        self._target_center = target_center
        self._trend = 0.0

    def set_bounds(self, min_val: float, max_val: float) -> None:
        self.min_val = min_val
        self.max_val = max_val
        self._current_val = max(min_val, min(max_val, self._current_val))

    def next_reading(self) -> dict[str, Any]:
        """Generate next smooth reading bounded between min_val and max_val."""
        # Mean-reverting random walk with bounded step noise
        drift = (self._target_center - self._current_val) * 0.05
        noise = random.uniform(-1.5, 1.5)
        self._trend = 0.8 * self._trend + 0.2 * (drift + noise)

        raw_val = self._current_val + self._trend
        clamped_val = max(self.min_val, min(self.max_val, raw_val))
        self._current_val = clamped_val

        rounded_val = round(clamped_val, 1)
        status = classify_gas_status(rounded_val)

        return {
            "sensor_id": "gas-01",
            "sensor_type": "gas",
            "value": rounded_val,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "local_simulator",
        }


class GasSensorService:
    """Background service manager broadcasting local gas sensor updates via telemetry WebSocket."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._generator = GasSensorGenerator()
        self._latest_reading: dict[str, Any] | None = None

    def start(self) -> None:
        """Start the background gas sensor loop if enabled."""
        settings = get_settings()
        if not settings.gas_sensor_enabled:
            logger.info("Gas sensor generator service disabled by configuration.")
            return

        if self._task is not None and not self._task.done():
            return

        self._generator.set_bounds(settings.gas_sensor_min, settings.gas_sensor_max)

        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_loop())
            logger.info("Started local gas sensor generator background service.")
        except RuntimeError:
            logger.warning("No running asyncio loop found when starting gas sensor service.")

    async def stop(self) -> None:
        """Stop the background gas sensor loop."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception) as exc:  # noqa: BLE001
                logger.debug("Gas sensor background task stopped: %s", exc)
            self._task = None
            logger.info("Stopped local gas sensor generator background service.")

    def get_latest_reading(self) -> dict[str, Any]:
        """Return latest generated reading or generate initial fallback."""
        if self._latest_reading is None:
            settings = get_settings()
            self._generator.set_bounds(settings.gas_sensor_min, settings.gas_sensor_max)
            self._latest_reading = self._generator.next_reading()
        return self._latest_reading

    async def _run_loop(self) -> None:
        """Background loop broadcasting gas telemetry at configured intervals."""
        try:
            while True:
                settings = get_settings()
                if not settings.gas_sensor_enabled:
                    await asyncio.sleep(1.0)
                    continue

                self._generator.set_bounds(settings.gas_sensor_min, settings.gas_sensor_max)
                reading = self._generator.next_reading()
                self._latest_reading = reading

                # Broadcast through existing telemetry WebSocket envelope
                payload = {
                    "type": "telemetry",
                    "data": {
                        "robot_id": "ROV-01",
                        "timestamp": reading["timestamp"],
                        "state": "IDLE",
                        "gas": reading,
                    },
                }
                await telemetry_broadcaster.broadcast(payload)
                await asyncio.sleep(settings.gas_sensor_interval_s)

        except asyncio.CancelledError:
            logger.debug("Gas sensor background loop cancelled.")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("Unhandled error in gas sensor loop: %s", exc)


gas_sensor_service = GasSensorService()
