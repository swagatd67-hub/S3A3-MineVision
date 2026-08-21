"""Lifecycle Manager for Pipe Cleaning Operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from cleaning.exceptions import (
    CleaningConcurrencyError,
    CleaningNotFoundError,
    CleaningStateError,
    InvalidOperationError,
)
from cleaning.models import CleaningMode, CleaningOperation, CleaningStatus


class CleaningOperationTracker:
    """Deterministic lifecycle tracker and coordinator for sewer pipe cleaning operations."""

    def __init__(self) -> None:
        self._operations: dict[str, CleaningOperation] = {}
        self._active_by_mission: dict[str, str] = {}

    def start_operation(
        self,
        operation_id: str,
        mission_id: str,
        mode: str = CleaningMode.DEFAULT.value,
        start_timestamp: datetime | None = None,
        start_distance_m: float | None = None,
        source: str = "operator",
        controller: Any | None = None,
    ) -> CleaningOperation:
        """Start a new cleaning operation.

        Parameters:
            operation_id: Unique operation identifier.
            mission_id: Target mission identifier.
            mode: Cleaning mode string (e.g. FLUSH, SCRUB, CUTTER, VACUUM, DEFAULT).
            start_timestamp: Optional start time.
            start_distance_m: Optional start location along pipe.
            source: Operation initiator.
            controller: Optional RobotController instance to issue hardware CLEAN_START command.

        Raises:
            InvalidOperationError: If operation_id already exists.
            CleaningConcurrencyError: If an active operation already exists for mission_id.
        """
        if operation_id in self._operations:
            raise InvalidOperationError(
                f"Cleaning operation '{operation_id}' already exists."
            )

        if mission_id in self._active_by_mission:
            active_id = self._active_by_mission[mission_id]
            raise CleaningConcurrencyError(
                f"Mission '{mission_id}' already has active cleaning operation '{active_id}'."
            )

        # Trigger hardware command via RobotController if provided
        if controller is not None and hasattr(controller, "clean_start"):
            controller.clean_start(mode)

        op = CleaningOperation(
            operation_id=operation_id,
            mission_id=mission_id,
            mode=mode,
            status=CleaningStatus.ACTIVE.value,
            start_timestamp=start_timestamp,
            end_timestamp=None,
            start_distance_m=start_distance_m,
            end_distance_m=None,
            source=source,
        )

        self._operations[operation_id] = op
        self._active_by_mission[mission_id] = operation_id
        return op

    def stop_operation(
        self,
        operation_id: str,
        stop_timestamp: datetime | None = None,
        end_distance_m: float | None = None,
        controller: Any | None = None,
    ) -> CleaningOperation:
        """Stop an active cleaning operation."""
        op = self.get_operation(operation_id)

        if op.status != CleaningStatus.ACTIVE.value:
            raise CleaningStateError(
                f"Cannot stop cleaning operation '{operation_id}' in state '{op.status}'. "
                "Only ACTIVE operations can be stopped."
            )

        # Trigger hardware command via RobotController if provided
        if controller is not None and hasattr(controller, "clean_stop"):
            controller.clean_stop()

        stopped_op = op.with_status(
            new_status=CleaningStatus.STOPPED.value,
            end_timestamp=stop_timestamp,
            end_distance_m=end_distance_m,
        )

        self._operations[operation_id] = stopped_op
        if self._active_by_mission.get(op.mission_id) == operation_id:
            del self._active_by_mission[op.mission_id]

        return stopped_op

    def complete_operation(
        self,
        operation_id: str,
        end_timestamp: datetime | None = None,
        end_distance_m: float | None = None,
    ) -> CleaningOperation:
        """Complete an active or stopped cleaning operation."""
        op = self.get_operation(operation_id)

        if op.status not in (CleaningStatus.ACTIVE.value, CleaningStatus.STOPPED.value):
            raise CleaningStateError(
                f"Cannot complete cleaning operation '{operation_id}' in state '{op.status}'."
            )

        completed_op = op.with_status(
            new_status=CleaningStatus.COMPLETED.value,
            end_timestamp=end_timestamp,
            end_distance_m=end_distance_m,
        )

        self._operations[operation_id] = completed_op
        if self._active_by_mission.get(op.mission_id) == operation_id:
            del self._active_by_mission[op.mission_id]

        return completed_op

    def fail_operation(
        self,
        operation_id: str,
        end_timestamp: datetime | None = None,
        reason: str = "",
    ) -> CleaningOperation:
        """Mark a cleaning operation as failed."""
        op = self.get_operation(operation_id)

        if op.status in (CleaningStatus.COMPLETED.value, CleaningStatus.FAILED.value):
            raise CleaningStateError(
                f"Cannot fail cleaning operation '{operation_id}' already in terminal state '{op.status}'."
            )

        failed_op = op.with_status(
            new_status=CleaningStatus.FAILED.value,
            end_timestamp=end_timestamp,
        )

        self._operations[operation_id] = failed_op
        if self._active_by_mission.get(op.mission_id) == operation_id:
            del self._active_by_mission[op.mission_id]

        return failed_op

    def get_operation(self, operation_id: str) -> CleaningOperation:
        """Retrieve operation by ID or raise CleaningNotFoundError."""
        if operation_id not in self._operations:
            raise CleaningNotFoundError(
                f"Cleaning operation '{operation_id}' not found."
            )
        return self._operations[operation_id]

    def get_active_operation(self, mission_id: str) -> CleaningOperation | None:
        """Retrieve active operation for mission_id if one exists."""
        op_id = self._active_by_mission.get(mission_id)
        if op_id is not None:
            return self._operations.get(op_id)
        return None

    def list_operations(self, mission_id: str | None = None) -> tuple[CleaningOperation, ...]:
        """List all tracked cleaning operations, optionally filtered by mission_id."""
        if mission_id is not None:
            return tuple(
                op for op in self._operations.values() if op.mission_id == mission_id
            )
        return tuple(self._operations.values())
