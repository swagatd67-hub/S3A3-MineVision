"""Synchronization and State Aggregation Engine for Digital Twin."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.services.inspection.models import FusedInspectionObservation
from cleaning.models import CleaningEffectiveness, CleaningOperation
from digital_twin.exceptions import MissionMismatchError, StaleUpdateError
from digital_twin.models import (
    DigitalTwinMissionState,
    DigitalTwinRobotState,
    DigitalTwinState,
    SynchronizationStatus,
)
from mapping.models import PipeInspectionMap
from morphology.models import MorphologySummaryReport
from robot.localization.models import RobotPose
from robot.telemetry.models import RobotTelemetry


class DigitalTwinSynchronizer:
    """State aggregator synchronizing real-time telemetry, pose, inspection, morphology, and cleaning domain states."""

    def __init__(
        self,
        robot_id: str = "unknown",
        mission_id: str = "unknown",
        stale_telemetry_threshold_sec: float = 5.0,
        recent_observations_limit: int = 10,
    ) -> None:
        self.robot_id = robot_id
        self.mission_id = mission_id
        self.stale_telemetry_threshold_sec = stale_telemetry_threshold_sec
        self.recent_observations_limit = recent_observations_limit

        self._telemetry: RobotTelemetry | None = None
        self._pose: RobotPose | None = None
        self._latest_observations: list[FusedInspectionObservation] = []
        self._inspection_map: PipeInspectionMap | None = None
        self._morphology_summary: MorphologySummaryReport | None = None
        self._active_cleaning_operation: CleaningOperation | None = None
        self._latest_cleaning_effectiveness: CleaningEffectiveness | None = None
        self._notes: list[str] = []
        self._last_updated_at: datetime = datetime.now(timezone.utc)

    def _validate_mission(self, incoming_mission_id: str | None) -> None:
        if not incoming_mission_id or incoming_mission_id == "unknown":
            return
        if self.mission_id == "unknown":
            self.mission_id = incoming_mission_id
        elif incoming_mission_id != self.mission_id:
            raise MissionMismatchError(
                f"Incoming mission_id '{incoming_mission_id}' does not match digital twin mission_id '{self.mission_id}'."
            )

    def update_telemetry(self, telemetry: RobotTelemetry) -> DigitalTwinState:
        """Synchronize telemetry state, checking mission consistency and timestamp monotonicity."""
        self._validate_mission(telemetry.mission_id)

        if self.robot_id == "unknown" and telemetry.robot_id:
            self.robot_id = telemetry.robot_id

        # Timestamp monotonicity check
        if (
            self._telemetry is not None
            and self._telemetry.timestamp is not None
            and telemetry.timestamp is not None
            and telemetry.timestamp < self._telemetry.timestamp
        ):
            raise StaleUpdateError(
                f"Cannot update telemetry with older timestamp ({telemetry.timestamp.isoformat()}) "
                f"than current ({self._telemetry.timestamp.isoformat()})."
            )

        self._telemetry = telemetry
        self._last_updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    def update_pose(
        self, pose: RobotPose, mission_id: str | None = None
    ) -> DigitalTwinState:
        """Synchronize robot localization pose."""
        if mission_id is not None:
            self._validate_mission(mission_id)

        # Monotonicity check
        if (
            self._pose is not None
            and hasattr(self._pose, "timestamp")
            and hasattr(pose, "timestamp")
        ):
            cur_ts: Any = getattr(self._pose, "timestamp", None)
            new_ts: Any = getattr(pose, "timestamp", None)
            if (
                isinstance(cur_ts, datetime)
                and isinstance(new_ts, datetime)
                and new_ts < cur_ts
            ):
                raise StaleUpdateError("Cannot update pose with older timestamp.")

        self._pose = pose
        self._last_updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    def add_observation(
        self, obs: FusedInspectionObservation
    ) -> DigitalTwinState:
        """Incorporate a new fused inspection observation into recent window."""
        self._validate_mission(obs.mission_id)

        self._latest_observations.append(obs)
        if len(self._latest_observations) > self.recent_observations_limit:
            self._latest_observations = self._latest_observations[
                -self.recent_observations_limit :
            ]

        self._last_updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    def update_inspection_map(
        self, inspection_map: PipeInspectionMap
    ) -> DigitalTwinState:
        """Synchronize spatial pipe inspection map."""
        self._validate_mission(inspection_map.mission_id)
        self._inspection_map = inspection_map
        self._last_updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    def update_morphology(
        self, morphology_summary: MorphologySummaryReport
    ) -> DigitalTwinState:
        """Synchronize pipe morphology summary."""
        self._validate_mission(morphology_summary.mission_id)
        self._morphology_summary = morphology_summary
        self._last_updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    def update_cleaning(
        self,
        cleaning_op: CleaningOperation | None = None,
        effectiveness: CleaningEffectiveness | None = None,
    ) -> DigitalTwinState:
        """Synchronize active cleaning operation and/or cleaning effectiveness."""
        if cleaning_op is not None:
            self._validate_mission(cleaning_op.mission_id)
            self._active_cleaning_operation = cleaning_op

        if effectiveness is not None:
            self._validate_mission(effectiveness.mission_id)
            self._latest_cleaning_effectiveness = effectiveness

        self._last_updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    def snapshot(self, now: datetime | None = None) -> DigitalTwinState:
        """Generate an immutable DigitalTwinState snapshot."""
        now_ts = now if now is not None else datetime.now(timezone.utc)

        freshness_sec: float | None = None
        if self._telemetry is not None and self._telemetry.timestamp is not None:
            freshness_sec = (now_ts - self._telemetry.timestamp).total_seconds()

        # Determine synchronization status
        notes: list[str] = []
        if self._telemetry is None and self._pose is None:
            sync_status = SynchronizationStatus.INITIALIZING.value
            notes.append("No telemetry or pose data received yet.")
        elif (
            freshness_sec is not None
            and freshness_sec > self.stale_telemetry_threshold_sec
        ):
            sync_status = SynchronizationStatus.STALE.value
            notes.append(
                f"Telemetry is stale ({round(freshness_sec, 1)}s old > threshold {self.stale_telemetry_threshold_sec}s)."
            )
        elif (
            self._pose is not None
            and getattr(self._pose.quality, "value", str(self._pose.quality))
            == "INVALID"
        ):
            sync_status = SynchronizationStatus.DEGRADED.value
            notes.append("Localization quality is DEGRADED/INVALID.")
        else:
            sync_status = SynchronizationStatus.SYNCHRONIZED.value

        # Robot state calculation
        robot_state: DigitalTwinRobotState | None = None
        if self._telemetry is not None or self._pose is not None:
            op_state = self._telemetry.state if self._telemetry is not None else "UNKNOWN"
            battery = self._telemetry.battery_percent if self._telemetry is not None else None
            body_diam = self._telemetry.body_diameter_mm if self._telemetry is not None else None
            tele_ts = self._telemetry.timestamp if self._telemetry is not None else None

            dist_m: float = 0.0
            if self._pose is not None:
                dist_m = float(self._pose.distance_m)
            elif self._telemetry is not None and self._telemetry.distance_m is not None:
                dist_m = float(self._telemetry.distance_m)

            robot_state = DigitalTwinRobotState(
                robot_id=self.robot_id,
                operational_state=op_state,
                battery_percent=battery,
                distance_m=dist_m,
                body_diameter_mm=body_diam,
                pose=self._pose,
                telemetry_timestamp=tele_ts,
                telemetry_freshness_sec=freshness_sec,
                telemetry=self._telemetry,
            )

        # Mission state calculation
        mission_state: DigitalTwinMissionState | None = None
        if self.mission_id != "unknown":
            cur_dist = robot_state.distance_m if robot_state is not None else 0.0
            total_inspected = (
                float(self._inspection_map.total_inspected_distance_m)
                if self._inspection_map is not None
                else cur_dist
            )
            start_d = (
                self._inspection_map.start_distance_m
                if self._inspection_map is not None
                else None
            )
            end_d = (
                self._inspection_map.end_distance_m
                if self._inspection_map is not None
                else None
            )
            obs_cnt = (
                self._inspection_map.observation_count
                if self._inspection_map is not None
                else len(self._latest_observations)
            )

            mission_state = DigitalTwinMissionState(
                mission_id=self.mission_id,
                current_distance_m=cur_dist,
                total_inspected_distance_m=total_inspected,
                start_distance_m=start_d,
                end_distance_m=end_d,
                observation_count=obs_cnt,
            )

        return DigitalTwinState(
            robot_id=self.robot_id,
            mission_id=self.mission_id,
            last_updated_at=self._last_updated_at,
            synchronization_status=sync_status,
            robot_state=robot_state,
            mission_state=mission_state,
            latest_observations=tuple(self._latest_observations),
            inspection_map=self._inspection_map,
            morphology_summary=self._morphology_summary,
            active_cleaning_operation=self._active_cleaning_operation,
            latest_cleaning_effectiveness=self._latest_cleaning_effectiveness,
            synchronization_notes=tuple(notes),
        )
