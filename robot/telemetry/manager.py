"""Telemetry Manager and Heartbeat Freshness Tracker."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from robot.telemetry.exceptions import TelemetryError, TelemetryParseError
from robot.telemetry.models import RobotTelemetry
from robot.telemetry.parser import parse_telemetry
from robot.transport.base import RobotTransport


class TelemetryManagerStatus(str, Enum):
    """Telemetry Manager operational status."""

    NO_DATA = "NO_DATA"
    TELEMETRY_RECEIVED = "TELEMETRY_RECEIVED"
    TRANSPORT_DISCONNECTED = "TRANSPORT_DISCONNECTED"
    PARSE_FAILURE = "PARSE_FAILURE"


class TelemetryManager:
    """Manages telemetry collection, state tracking, and heartbeat freshness."""

    def __init__(self, transport: RobotTransport | None = None) -> None:
        self._transport = transport
        self._latest_telemetry: RobotTelemetry | None = None
        self._last_received_at: datetime | None = None
        self._last_telemetry_timestamp: datetime | None = None
        self._status: TelemetryManagerStatus = TelemetryManagerStatus.NO_DATA
        self._last_error: TelemetryError | None = None

    @property
    def transport(self) -> RobotTransport | None:
        return self._transport

    @property
    def latest_telemetry(self) -> RobotTelemetry | None:
        return self._latest_telemetry

    @property
    def last_received_at(self) -> datetime | None:
        return self._last_received_at

    @property
    def last_telemetry_timestamp(self) -> datetime | None:
        return self._last_telemetry_timestamp

    @property
    def status(self) -> TelemetryManagerStatus:
        return self._status

    @property
    def last_error(self) -> TelemetryError | None:
        return self._last_error

    def process_raw(
        self,
        raw: dict[str, Any] | str | None,
        receive_time: datetime | None = None,
    ) -> RobotTelemetry | None:
        """Process raw telemetry dictionary or JSON string.

        Updates internal status, latest telemetry model, and timestamps.
        """
        if raw is None:
            if self._transport is not None and not self._transport.is_connected:
                self._status = TelemetryManagerStatus.TRANSPORT_DISCONNECTED
            elif self._latest_telemetry is None:
                self._status = TelemetryManagerStatus.NO_DATA
            return None

        try:
            telemetry = parse_telemetry(raw)
        except TelemetryError as err:
            self._status = TelemetryManagerStatus.PARSE_FAILURE
            self._last_error = err
            raise

        if telemetry is None:
            if self._latest_telemetry is None:
                self._status = TelemetryManagerStatus.NO_DATA
            return None

        now = receive_time or datetime.now(timezone.utc)
        self._latest_telemetry = telemetry
        self._last_received_at = now
        self._last_telemetry_timestamp = telemetry.timestamp
        self._status = TelemetryManagerStatus.TELEMETRY_RECEIVED
        self._last_error = None
        return telemetry

    def poll(
        self,
        timeout: float | None = 0.0,
        receive_time: datetime | None = None,
    ) -> RobotTelemetry | None:
        """Poll transport for raw telemetry message and process it."""
        if self._transport is None:
            raise RuntimeError("No transport configured for TelemetryManager poll.")

        if not self._transport.is_connected:
            self._status = TelemetryManagerStatus.TRANSPORT_DISCONNECTED
            return None

        try:
            raw = self._transport.receive(timeout=timeout)
            return self.process_raw(raw, receive_time=receive_time)
        except Exception as exc:
            self._status = TelemetryManagerStatus.PARSE_FAILURE
            if isinstance(exc, TelemetryError):
                self._last_error = exc
                raise
            err = TelemetryParseError(f"Transport error during receive: {exc}")
            self._last_error = err
            raise err from exc

    def is_stale(
        self,
        timeout_seconds: float,
        current_time: datetime | None = None,
    ) -> bool:
        """Return True if telemetry is stale or never received."""
        if self._last_received_at is None:
            return True
        now = current_time or datetime.now(timezone.utc)
        elapsed = (now - self._last_received_at).total_seconds()
        return elapsed > timeout_seconds

    def is_fresh(
        self,
        timeout_seconds: float,
        current_time: datetime | None = None,
    ) -> bool:
        """Return True if telemetry was received within timeout_seconds."""
        return not self.is_stale(timeout_seconds, current_time=current_time)
