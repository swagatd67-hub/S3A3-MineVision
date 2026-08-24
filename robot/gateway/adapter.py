"""PipeVision Robot Gateway and Hardware Adapter Implementation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from backend.app.services.inspection.models import (
    CanonicalInspectionFrame,
    SingleIngestionResult,
)
from robot.control.robot_controller import (
    ControllerError,
    ControllerState,
    RobotController,
)
from robot.gateway.exceptions import (
    RobotGatewayConnectionError,
    RobotGatewayValidationError,
)
from robot.gateway.models import (
    GatewayConnectionState,
    GatewayFailureReason,
    GatewayHealth,
    HardwareFramePacket,
)
from robot.gateway.queue import BoundedFrameQueue
from robot.localization.models import RobotPose
from robot.telemetry.exceptions import TelemetryError
from robot.telemetry.models import RobotTelemetry
from robot.telemetry.parser import parse_telemetry
from robot.transport.base import RobotTransport

if TYPE_CHECKING:
    from robot.localization.localizer import RobotLocalizer

logger = logging.getLogger(__name__)


class RobotGatewayAdapter:
    """Thin input adapter connecting physical/simulated robot hardware to PipeVision contracts.

    Responsibilities:
      - Manage connection lifecycle (DISCONNECTED, CONNECTING, CONNECTED, STREAMING, DISCONNECTING).
      - Normalize raw hardware telemetry into standard RobotTelemetry.
      - Update localization (RobotPose) via RobotLocalizer or direct hardware pose updates.
      - Transform camera frames into CanonicalInspectionFrame and route to Phase 11 gateway.
      - Direct commands safely through RobotController and commands.json schema.
      - Expose real-time connection health, frame/telemetry counters, and timeout diagnostics.
    """

    def __init__(
        self,
        transport: RobotTransport,
        controller: RobotController | None = None,
        robot_id: str | None = None,
        mission_id: str | None = None,
        localizer: RobotLocalizer | None = None,
        telemetry_timeout_s: float = 5.0,
        frame_timeout_s: float = 10.0,
        auto_ingest_backend: bool = True,
        frame_queue: BoundedFrameQueue | None = None,
    ) -> None:
        self.transport = transport
        self.controller = controller or RobotController(transport)
        self.robot_id = robot_id
        self.mission_id = mission_id
        self.localizer = localizer
        self.telemetry_timeout_s = telemetry_timeout_s
        self.frame_timeout_s = frame_timeout_s
        self.auto_ingest_backend = auto_ingest_backend
        self.frame_queue = frame_queue

        self._connection_state = GatewayConnectionState.DISCONNECTED
        self._failure_reason = GatewayFailureReason.NONE
        self._last_telemetry_timestamp: datetime | None = None
        self._last_frame_timestamp: datetime | None = None
        self._latest_telemetry: RobotTelemetry | None = None
        self._latest_pose: RobotPose | None = None
        self._telemetry_packet_count = 0
        self._frame_count = 0
        self._dropped_frame_count = 0
        self._error_count = 0

    @property
    def connection_state(self) -> GatewayConnectionState:
        """Current connection lifecycle state."""
        return self._connection_state

    @property
    def failure_reason(self) -> GatewayFailureReason:
        """Current failure reason code."""
        return self._failure_reason

    @property
    def is_connected(self) -> bool:
        """True if gateway is CONNECTED or STREAMING and underlying controller is active."""
        return (
            self._connection_state
            in (GatewayConnectionState.CONNECTED, GatewayConnectionState.STREAMING)
            and self.controller.is_connected
        )

    @property
    def latest_telemetry(self) -> RobotTelemetry | None:
        """Latest normalized telemetry packet."""
        return self._latest_telemetry

    @property
    def latest_pose(self) -> RobotPose | None:
        """Latest localization pose."""
        return self._latest_pose

    def connect(
        self,
        robot_id: str | None = None,
        mission_id: str | None = None,
    ) -> None:
        """Establish gateway connection to robot hardware/transport."""
        if robot_id is not None:
            self.robot_id = robot_id
        if mission_id is not None:
            self.mission_id = mission_id

        self._connection_state = GatewayConnectionState.CONNECTING

        try:
            if not self.controller.is_connected:
                self.controller.connect()
            self._connection_state = GatewayConnectionState.CONNECTED
            self._failure_reason = GatewayFailureReason.NONE
        except (ControllerError, Exception) as exc:
            self._connection_state = GatewayConnectionState.DISCONNECTED
            self._failure_reason = GatewayFailureReason.CONNECTION_FAILED
            self._error_count += 1
            raise RobotGatewayConnectionError(
                f"Failed to connect robot gateway: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Disconnect gateway and cleanly stop hardware controller."""
        if self._connection_state == GatewayConnectionState.DISCONNECTED:
            return

        self._connection_state = GatewayConnectionState.DISCONNECTING
        try:
            self.controller.disconnect()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error disconnecting controller: %s", exc)
        finally:
            self._connection_state = GatewayConnectionState.DISCONNECTED

    def ingest_telemetry_payload(
        self,
        raw_payload: dict[str, Any] | str | None,
        db: Session | None = None,
    ) -> RobotTelemetry | None:
        """Validate, normalize, and ingest raw hardware telemetry payload."""
        if raw_payload is None:
            return None

        try:
            telemetry = parse_telemetry(raw_payload)
        except TelemetryError as exc:
            self._error_count += 1
            self._failure_reason = GatewayFailureReason.INVALID_DATA
            raise RobotGatewayValidationError(
                f"Malformed hardware telemetry: {exc}"
            ) from exc

        if telemetry is None:
            return None

        # Validate identity matching if expected
        if self.robot_id is not None and telemetry.robot_id != self.robot_id:
            self._error_count += 1
            self._failure_reason = GatewayFailureReason.MISSION_MISMATCH
            raise RobotGatewayValidationError(
                f"Telemetry robot_id '{telemetry.robot_id}' does not match expected gateway robot_id '{self.robot_id}'."
            )

        if self.robot_id is None:
            self.robot_id = telemetry.robot_id

        if (
            self.mission_id is not None
            and telemetry.mission_id is not None
            and telemetry.mission_id != self.mission_id
        ):
            self._error_count += 1
            self._failure_reason = GatewayFailureReason.MISSION_MISMATCH
            raise RobotGatewayValidationError(
                f"Telemetry mission_id '{telemetry.mission_id}' does not match active gateway mission_id '{self.mission_id}'."
            )

        if self.mission_id is None and telemetry.mission_id is not None:
            self.mission_id = telemetry.mission_id

        # Update localizer if configured
        if self.localizer is not None:
            self._latest_pose = self.localizer.update(telemetry)

        ts = telemetry.timestamp or datetime.now(timezone.utc)
        self._latest_telemetry = telemetry
        self._last_telemetry_timestamp = ts
        self._telemetry_packet_count += 1

        if self._connection_state == GatewayConnectionState.CONNECTED:
            self._connection_state = GatewayConnectionState.STREAMING
        self._failure_reason = GatewayFailureReason.NONE

        # Ingest to Backend Mission Orchestrator if requested
        if db is not None and self.mission_id and self.auto_ingest_backend:
            from backend.app.services.mission.orchestrator import MissionOrchestrator

            raw_dict = (
                raw_payload
                if isinstance(raw_payload, dict)
                else {"robot_id": telemetry.robot_id, "mission_id": telemetry.mission_id}
            )
            try:
                MissionOrchestrator().ingest_telemetry(db, self.mission_id, raw_dict)
                if self._latest_pose is not None:
                    MissionOrchestrator().ingest_pose(db, self.mission_id, self._latest_pose)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Backend telemetry ingestion failed: %s", exc)

        return telemetry

    def ingest_pose(
        self,
        pose: RobotPose,
        db: Session | None = None,
    ) -> RobotPose:
        """Ingest direct or externally provided RobotPose localization update."""
        self._latest_pose = pose

        if db is not None and self.mission_id and self.auto_ingest_backend:
            from backend.app.services.mission.orchestrator import MissionOrchestrator

            try:
                MissionOrchestrator().ingest_pose(db, self.mission_id, pose)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Backend pose ingestion failed: %s", exc)

        return pose

    def get_current_pose(self) -> RobotPose | None:
        """Return the current RobotPose from localizer or direct hardware pose update."""
        return self._latest_pose

    def ingest_camera_frame(
        self,
        frame_input: HardwareFramePacket | dict[str, Any],
        db: Session | None = None,
    ) -> SingleIngestionResult:
        """Ingest a camera frame, converting it to CanonicalInspectionFrame for Phase 11 inspection."""
        packet: HardwareFramePacket
        if isinstance(frame_input, dict):
            try:
                packet = HardwareFramePacket(**frame_input)
            except Exception as exc:
                self._error_count += 1
                self._failure_reason = GatewayFailureReason.INVALID_DATA
                raise RobotGatewayValidationError(
                    f"Invalid HardwareFramePacket dictionary: {exc}"
                ) from exc
        elif isinstance(frame_input, HardwareFramePacket):
            packet = frame_input
        else:
            self._error_count += 1
            self._failure_reason = GatewayFailureReason.INVALID_DATA
            raise RobotGatewayValidationError(
                f"Expected HardwareFramePacket or dict, got {type(frame_input).__name__}."
            )

        mission_id = self.mission_id or (
            packet.metadata.get("mission_id") if packet.metadata else None
        )
        if not mission_id:
            self._error_count += 1
            self._failure_reason = GatewayFailureReason.MISSION_MISMATCH
            raise RobotGatewayValidationError(
                "Frame ingestion requires an active mission_id."
            )

        robot_id = self.robot_id or (
            packet.metadata.get("robot_id") if packet.metadata else None
        )

        distance_m = packet.distance_m
        if distance_m is None and self._latest_telemetry is not None:
            distance_m = self._latest_telemetry.distance_m
        if distance_m is None and self._latest_pose is not None:
            distance_m = self._latest_pose.distance_m

        pose = packet.pose or self._latest_pose

        canonical_frame = CanonicalInspectionFrame(
            mission_id=mission_id,
            robot_id=robot_id,
            frame_id=packet.frame_id,
            camera_id=packet.camera_id,
            timestamp=packet.timestamp or self._last_telemetry_timestamp,
            source=packet.source or "live",
            frame_index=packet.frame_index,
            image_bytes=packet.image_bytes,
            distance_m=distance_m,
            pose=pose,
            metadata=packet.metadata,
        )

        ts = (
            packet.timestamp
            if isinstance(packet.timestamp, datetime)
            else datetime.now(timezone.utc)
        )
        self._last_frame_timestamp = ts
        self._frame_count += 1

        if db is not None:
            from backend.app.services.inspection.gateway import (
                ingest_inspection_frame,
            )

            return ingest_inspection_frame(db, canonical_frame)

        return SingleIngestionResult(
            mission_id=mission_id,
            frame_id=packet.frame_id or f"frame-{packet.frame_index:06d}",
            frame_index=packet.frame_index,
            timestamp_iso=ts.isoformat(),
            source=packet.source or "live",
            distance_m=distance_m,
            frame_path=None,
            observations=[],
        )

    def poll(
        self,
        db: Session | None = None,
        timeout: float | None = 0.0,
    ) -> RobotTelemetry | None:
        """Poll hardware transport non-blockingly for incoming telemetry packets."""
        if self._connection_state == GatewayConnectionState.DISCONNECTED:
            return None

        try:
            raw = self.controller.poll()
        except ControllerError as exc:
            self._connection_state = GatewayConnectionState.DISCONNECTED
            self._failure_reason = GatewayFailureReason.TRANSPORT_ERROR
            self._error_count += 1
            raise RobotGatewayConnectionError(
                f"Transport error during poll: {exc}"
            ) from exc

        if raw is not None:
            return self.ingest_telemetry_payload(raw, db=db)

        # Check telemetry timeout if streaming
        if (
            self._connection_state == GatewayConnectionState.STREAMING
            and self._last_telemetry_timestamp is not None
        ):
            now = datetime.now(timezone.utc)
            delta = (now - self._last_telemetry_timestamp).total_seconds()
            if delta > self.telemetry_timeout_s:
                self._failure_reason = GatewayFailureReason.TELEMETRY_TIMEOUT

        return self._latest_telemetry

    def move(self, linear: float, angular: float) -> None:
        """Send movement command to physical robot via RobotController."""
        self.controller.move(linear, angular)

    def stop(self) -> None:
        """Send stop command to physical robot via RobotController."""
        self.controller.stop()

    def emergency_stop(self) -> None:
        """Trigger immediate safety emergency stop via RobotController."""
        self.controller.emergency_stop()

    def camera_pan(self, angle_deg: float) -> None:
        """Send camera pan command via RobotController."""
        self.controller.camera_pan(angle_deg)

    def clean_start(self, mode: str) -> None:
        """Start cleaning operation via RobotController."""
        self.controller.clean_start(mode)

    def clean_stop(self) -> None:
        """Stop cleaning operation via RobotController."""
        self.controller.clean_stop()

    def sample_open(self) -> None:
        """Open sampling mechanism via RobotController."""
        self.controller.sample_open()

    def sample_close(self) -> None:
        """Close sampling mechanism via RobotController."""
        self.controller.sample_close()

    def inflate(self, target_pressure_kpa: float) -> None:
        """Inflate crawler element via RobotController."""
        self.controller.inflate(target_pressure_kpa)

    def deflate(self) -> None:
        """Deflate crawler element via RobotController."""
        self.controller.deflate()

    def hold_pressure(self, target_pressure_kpa: float) -> None:
        """Hold pressure in crawler element via RobotController."""
        self.controller.hold_pressure(target_pressure_kpa)

    def get_health(self) -> GatewayHealth:
        """Retrieve connection health, packet counters, and diagnostic status snapshot."""
        now = datetime.now(timezone.utc)
        telem_timeout = False
        frame_timeout = False

        if (
            self._connection_state == GatewayConnectionState.STREAMING
            and self._last_telemetry_timestamp is not None
            and (now - self._last_telemetry_timestamp).total_seconds() > self.telemetry_timeout_s
        ):
            telem_timeout = True

        if (
            self._last_frame_timestamp is not None
            and (now - self._last_frame_timestamp).total_seconds() > self.frame_timeout_s
        ):
            frame_timeout = True

        effective_failure = self._failure_reason
        if telem_timeout and effective_failure == GatewayFailureReason.NONE:
            effective_failure = GatewayFailureReason.TELEMETRY_TIMEOUT
        elif frame_timeout and effective_failure == GatewayFailureReason.NONE:
            effective_failure = GatewayFailureReason.FRAME_TIMEOUT

        is_healthy = (
            self.is_connected
            and effective_failure == GatewayFailureReason.NONE
            and self.controller.state not in (ControllerState.FAULT, ControllerState.EMERGENCY_STOP)
        )

        transport_type = type(self.transport).__name__

        queue_dropped = (
            self.frame_queue.get_metrics().total_dropped
            if self.frame_queue is not None
            else 0
        )

        return GatewayHealth(
            connection_state=self._connection_state,
            failure_reason=effective_failure,
            robot_id=self.robot_id,
            mission_id=self.mission_id,
            transport_type=transport_type,
            is_connected=self.is_connected,
            is_healthy=is_healthy,
            last_telemetry_timestamp=self._last_telemetry_timestamp,
            last_frame_timestamp=self._last_frame_timestamp,
            telemetry_packet_count=self._telemetry_packet_count,
            frame_count=self._frame_count,
            dropped_frame_count=self._dropped_frame_count + queue_dropped,
            error_count=self._error_count,
        )
