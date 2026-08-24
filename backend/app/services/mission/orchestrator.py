"""Mission Orchestration Service for PipeVision Backend.

Coordinates cross-domain workflows: Robot Telemetry, Localization, Inspection Fusion,
Inspection Mapping, Morphology Analysis, Cleaning Domain, and Digital Twin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Self
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models import InspectionObservationRow, Mission, Robot
from backend.app.services.inspection.models import FusedInspectionObservation
from backend.app.services.mission.exceptions import (
    InvalidMissionLifecycleError,
    MissionNotFoundError,
    RobotMismatchError,
)
from backend.app.services.mission.models import (
    MissionLifecycleState,
    MissionProgressMetrics,
    MissionSnapshot,
)
from cleaning.models import CleaningEffectiveness, CleaningOperation
from digital_twin.models import DigitalTwinState
from digital_twin.synchronizer import DigitalTwinSynchronizer
from mapping.builder import build_inspection_map
from mapping.models import PipeInspectionMap
from morphology import analyze_morphology
from morphology.models import MorphologyCalibration, MorphologySummaryReport
from robot.localization.models import RobotPose
from robot.telemetry.models import RobotTelemetry
from robot.telemetry.parser import parse_telemetry


class MissionOrchestrator:
    """Central singleton orchestrator coordinating all PipeVision domains for a mission."""

    _instance: Self | None = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._initialized = False
            cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        # In-memory domain state caches indexed by mission_id
        self._twins: dict[str, DigitalTwinSynchronizer] = {}
        self._observations: dict[str, list[FusedInspectionObservation]] = {}
        self._telemetries: dict[str, list[RobotTelemetry]] = {}
        self._poses: dict[str, list[RobotPose]] = {}

    def create_mission(
        self,
        db: Session,
        robot_id: str,
        objective: str = "INSPECT",
        mission_id: str | None = None,
        notes: str | None = None,
    ) -> Mission:
        """Create a new mission with CREATED status."""
        robot = db.get(Robot, robot_id)
        if robot is None:
            raise RobotMismatchError(f"Robot '{robot_id}' is not registered.")

        final_mission_id = (
            mission_id or f"M-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
        )

        existing = db.get(Mission, final_mission_id)
        if existing is not None:
            return existing

        mission = Mission(
            mission_id=final_mission_id,
            robot_id=robot_id,
            objective=objective,
            status=MissionLifecycleState.CREATED.value,
            created_at=datetime.now(timezone.utc),
            notes=notes,
        )
        db.add(mission)
        db.commit()
        db.refresh(mission)

        # Initialize Digital Twin Synchronizer
        self._twins[final_mission_id] = DigitalTwinSynchronizer(
            robot_id=robot_id, mission_id=final_mission_id
        )
        self._observations[final_mission_id] = []
        self._telemetries[final_mission_id] = []
        self._poses[final_mission_id] = []

        return mission

    def start_mission(self, db: Session, mission_id: str) -> Mission:
        """Transition mission state to RUNNING."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        if mission.status == MissionLifecycleState.RUNNING.value:
            return mission  # Idempotent

        if not MissionLifecycleState.can_transition(mission.status, MissionLifecycleState.RUNNING.value):
            raise InvalidMissionLifecycleError(
                f"Cannot transition mission '{mission_id}' from '{mission.status}' to 'RUNNING'."
            )

        mission.status = MissionLifecycleState.RUNNING.value
        if mission.started_at is None:
            mission.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(mission)
        return mission

    def pause_mission(self, db: Session, mission_id: str) -> Mission:
        """Transition mission state to PAUSED."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        if mission.status == MissionLifecycleState.PAUSED.value:
            return mission

        if not MissionLifecycleState.can_transition(mission.status, MissionLifecycleState.PAUSED.value):
            raise InvalidMissionLifecycleError(
                f"Cannot transition mission '{mission_id}' from '{mission.status}' to 'PAUSED'."
            )

        mission.status = MissionLifecycleState.PAUSED.value
        db.commit()
        db.refresh(mission)
        return mission

    def resume_mission(self, db: Session, mission_id: str) -> Mission:
        """Resume a PAUSED mission to RUNNING."""
        return self.start_mission(db, mission_id)

    def complete_mission(self, db: Session, mission_id: str) -> Mission:
        """Transition mission state to COMPLETED."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        if mission.status == MissionLifecycleState.COMPLETED.value:
            return mission

        if not MissionLifecycleState.can_transition(mission.status, MissionLifecycleState.COMPLETED.value):
            raise InvalidMissionLifecycleError(
                f"Cannot transition mission '{mission_id}' from '{mission.status}' to 'COMPLETED'."
            )

        mission.status = MissionLifecycleState.COMPLETED.value
        mission.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(mission)
        return mission

    def cancel_mission(self, db: Session, mission_id: str) -> Mission:
        """Transition mission state to CANCELLED."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        if mission.status == MissionLifecycleState.CANCELLED.value:
            return mission

        if not MissionLifecycleState.can_transition(mission.status, MissionLifecycleState.CANCELLED.value):
            raise InvalidMissionLifecycleError(
                f"Cannot transition mission '{mission_id}' from '{mission.status}' to 'CANCELLED'."
            )

        mission.status = MissionLifecycleState.CANCELLED.value
        mission.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(mission)
        return mission

    def ingest_telemetry(
        self, db: Session, mission_id: str, telemetry_dict: dict[str, Any]
    ) -> DigitalTwinState:
        """Ingest raw robot telemetry packet and update Digital Twin."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        telemetry = parse_telemetry(telemetry_dict)
        if telemetry is None:
            raise ValueError("Failed to parse telemetry payload.")

        self._telemetries.setdefault(mission_id, []).append(telemetry)

        twin = self._twins.get(mission_id)
        if twin is None:
            twin = DigitalTwinSynchronizer(robot_id=mission.robot_id, mission_id=mission_id)
            self._twins[mission_id] = twin

        return twin.update_telemetry(telemetry)

    def ingest_pose(self, db: Session, mission_id: str, pose: RobotPose) -> DigitalTwinState:
        """Ingest localization RobotPose update and update Digital Twin."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        self._poses.setdefault(mission_id, []).append(pose)

        twin = self._twins.get(mission_id)
        if twin is None:
            twin = DigitalTwinSynchronizer(robot_id=mission.robot_id, mission_id=mission_id)
            self._twins[mission_id] = twin

        return twin.update_pose(pose, mission_id=mission_id)

    def ingest_inspection_observation(
        self, db: Session, mission_id: str, obs: FusedInspectionObservation
    ) -> DigitalTwinState:
        """Ingest fused inspection observation, persist to DB, and update Digital Twin."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        obs_list = self._observations.setdefault(mission_id, [])
        is_new = not any(o.observation_id == obs.observation_id for o in obs_list)

        if is_new:
            obs_list.append(obs)
            # Persist observation
            obs_row = InspectionObservationRow(
                observation_id=obs.observation_id,
                mission_id=mission_id,
                frame_index=obs.frame_index,
                timestamp=obs.timestamp,
                distance_m=obs.distance_m,
                class_code=obs.class_code,
                confidence=obs.confidence,
                localization_quality=obs.localization_quality,
                model_name=obs.model_name,
                model_version=obs.model_version,
                box=obs.box.to_dict() if obs.box is not None else None,
                robot_pose=(
                    {
                        "x": obs.robot_pose.x,
                        "y": obs.robot_pose.y,
                        "heading_deg": obs.robot_pose.heading_deg,
                        "quality": (
                            obs.robot_pose.quality.value
                            if hasattr(obs.robot_pose.quality, "value")
                            else str(obs.robot_pose.quality)
                        ),
                    }
                    if obs.robot_pose is not None
                    else None
                ),
            )
            db.merge(obs_row)
            db.commit()

        twin = self._twins.get(mission_id)
        if twin is None:
            twin = DigitalTwinSynchronizer(robot_id=mission.robot_id, mission_id=mission_id)
            self._twins[mission_id] = twin

        if is_new:
            return twin.add_observation(obs)
        return twin.snapshot()

    def update_mapping(self, db: Session, mission_id: str) -> PipeInspectionMap:
        """Rebuild spatial inspection map for mission and update Digital Twin."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        obs_list = self._observations.get(mission_id, [])
        inspection_map = build_inspection_map(obs_list, mission_id=mission_id)

        twin = self._twins.get(mission_id)
        if twin is not None:
            twin.update_inspection_map(inspection_map)

        return inspection_map

    def update_morphology(
        self,
        db: Session,
        mission_id: str,
        calibration: MorphologyCalibration | None = None,
    ) -> MorphologySummaryReport:
        """Execute morphology analyzer over mission observations and update Digital Twin."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        obs_list = self._observations.get(mission_id, [])
        report = analyze_morphology(obs_list, calibration=calibration)

        twin = self._twins.get(mission_id)
        if twin is not None:
            twin.update_morphology(report)

        return report

    def update_cleaning(
        self,
        db: Session,
        mission_id: str,
        operation: CleaningOperation | None = None,
        effectiveness: CleaningEffectiveness | None = None,
    ) -> DigitalTwinState:
        """Update active cleaning operation / effectiveness and sync Digital Twin."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        twin = self._twins.get(mission_id)
        if twin is None:
            twin = DigitalTwinSynchronizer(robot_id=mission.robot_id, mission_id=mission_id)
            self._twins[mission_id] = twin

        return twin.update_cleaning(cleaning_op=operation, effectiveness=effectiveness)

    def get_digital_twin_state(self, db: Session, mission_id: str) -> DigitalTwinState:
        """Retrieve current DigitalTwinState snapshot for mission."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        twin = self._twins.get(mission_id)
        if twin is None:
            twin = DigitalTwinSynchronizer(robot_id=mission.robot_id, mission_id=mission_id)
            self._twins[mission_id] = twin

        return twin.snapshot()

    def get_mission_snapshot(self, db: Session, mission_id: str) -> MissionSnapshot:
        """Build full mission snapshot combining lifecycle, progress, and Digital Twin."""
        mission = db.get(Mission, mission_id)
        if mission is None:
            raise MissionNotFoundError(f"Mission '{mission_id}' not found.")

        twin_state = self.get_digital_twin_state(db, mission_id)
        obs_list = self._observations.get(mission_id, [])

        cur_dist: float = 0.0
        if twin_state.robot_state is not None:
            cur_dist = twin_state.robot_state.distance_m

        total_inspected = (
            twin_state.mission_state.total_inspected_distance_m
            if twin_state.mission_state is not None
            else cur_dist
        )

        morphology_count = (
            twin_state.morphology_summary.measured_count
            if twin_state.morphology_summary is not None
            else 0
        )

        s_at = (
            mission.started_at.replace(tzinfo=timezone.utc)
            if mission.started_at and mission.started_at.tzinfo is None
            else mission.started_at
        )
        c_at = (
            mission.completed_at.replace(tzinfo=timezone.utc)
            if mission.completed_at and mission.completed_at.tzinfo is None
            else mission.completed_at
        )

        progress = MissionProgressMetrics(
            current_distance_m=cur_dist,
            total_inspected_distance_m=total_inspected,
            observation_count=len(obs_list),
            morphology_measurements_count=morphology_count,
            cleaning_operations_count=1 if twin_state.active_cleaning_operation else 0,
            duration_sec=(
                (c_at - s_at).total_seconds()
                if c_at and s_at
                else (
                    (datetime.now(timezone.utc) - s_at).total_seconds()
                    if s_at
                    else None
                )
            ),
        )

        return MissionSnapshot(
            mission_id=mission.mission_id,
            robot_id=mission.robot_id,
            objective=mission.objective,
            status=mission.status,
            created_at=mission.created_at,
            started_at=mission.started_at,
            completed_at=mission.completed_at,
            notes=mission.notes,
            progress=progress,
            digital_twin=twin_state.to_dict(),
        )


orchestrator = MissionOrchestrator()
