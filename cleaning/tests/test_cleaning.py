"""Comprehensive Unit Tests for Pipe Cleaning Operations & Effectiveness Domain."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.inspection import (
    InspectionFrameMetadata,
    RawPerceptionItem,
    fuse_observations,
)
from cleaning import (
    CleaningConcurrencyError,
    CleaningEffectiveness,
    CleaningMode,
    CleaningNotFoundError,
    CleaningOperation,
    CleaningOperationTracker,
    CleaningStateError,
    CleaningStatus,
    InvalidOperationError,
    evaluate_cleaning_effectiveness,
)
from mapping import build_inspection_map
from robot.control import RobotController
from robot.transport.simulator import SimulatorTransport


def test_cleaning_operation_model_creation_and_immutability() -> None:
    now = datetime.now(timezone.utc)
    op = CleaningOperation(
        operation_id="CLEAN-001",
        mission_id="MIS-100",
        mode=CleaningMode.FLUSH.value,
        status=CleaningStatus.REQUESTED.value,
        start_timestamp=now,
        end_timestamp=None,
        start_distance_m=10.0,
        end_distance_m=20.0,
        source="operator",
    )

    assert op.operation_id == "CLEAN-001"
    assert op.mission_id == "MIS-100"
    assert op.mode == "FLUSH"
    assert op.status == "REQUESTED"
    assert op.start_distance_m == 10.0
    assert op.end_distance_m == 20.0

    # Ensure immutability
    with pytest.raises(AttributeError):
        op.status = "ACTIVE"  # type: ignore[misc]

    # Test dictionary serialization
    d = op.to_dict()
    assert d["operation_id"] == "CLEAN-001"
    assert d["mode"] == "FLUSH"
    assert d["start_distance_m"] == 10.0


def test_cleaning_operation_validation_rules() -> None:
    now = datetime.now(timezone.utc)

    # Empty IDs
    with pytest.raises(InvalidOperationError, match="operation_id cannot be empty"):
        CleaningOperation("", "MIS-1", "DEFAULT", "ACTIVE", None, None, None, None)

    with pytest.raises(InvalidOperationError, match="mission_id cannot be empty"):
        CleaningOperation("OP-1", "", "DEFAULT", "ACTIVE", None, None, None, None)

    # End timestamp preceding start timestamp
    with pytest.raises(InvalidOperationError, match="cannot precede"):
        CleaningOperation(
            "OP-1",
            "MIS-1",
            "DEFAULT",
            "ACTIVE",
            now,
            now - timedelta(seconds=10),
            10.0,
            20.0,
        )

    # End distance less than start distance
    with pytest.raises(InvalidOperationError, match="cannot be less than"):
        CleaningOperation("OP-1", "MIS-1", "DEFAULT", "ACTIVE", now, None, 20.0, 10.0)

    # Negative distances
    with pytest.raises(InvalidOperationError, match="cannot be negative"):
        CleaningOperation("OP-1", "MIS-1", "DEFAULT", "ACTIVE", None, None, -5.0, 10.0)


def test_operation_tracker_lifecycle_flow() -> None:
    tracker = CleaningOperationTracker()
    now = datetime.now(timezone.utc)

    # Start operation
    op1 = tracker.start_operation(
        operation_id="OP-001",
        mission_id="MIS-100",
        mode=CleaningMode.SCRUB.value,
        start_timestamp=now,
        start_distance_m=5.0,
    )
    assert op1.status == CleaningStatus.ACTIVE.value
    assert tracker.get_active_operation("MIS-100") == op1

    # Stop operation
    stop_time = now + timedelta(minutes=5)
    stopped = tracker.stop_operation(
        operation_id="OP-001",
        stop_timestamp=stop_time,
        end_distance_m=15.0,
    )
    assert stopped.status == CleaningStatus.STOPPED.value
    assert stopped.end_distance_m == 15.0
    assert tracker.get_active_operation("MIS-100") is None

    # Complete operation
    completed = tracker.complete_operation(operation_id="OP-001")
    assert completed.status == CleaningStatus.COMPLETED.value


def test_operation_tracker_concurrency_and_invalid_transitions() -> None:
    tracker = CleaningOperationTracker()

    tracker.start_operation("OP-100", "MIS-CONCUR", mode="DEFAULT")

    # Cannot start a second active operation on the same mission
    with pytest.raises(CleaningConcurrencyError, match="already has active cleaning operation"):
        tracker.start_operation("OP-101", "MIS-CONCUR", mode="FLUSH")

    # Cannot start duplicate operation_id
    with pytest.raises(InvalidOperationError, match="already exists"):
        tracker.start_operation("OP-100", "MIS-OTHER", mode="FLUSH")

    # Stop operation
    tracker.stop_operation("OP-100")

    # Cannot stop already stopped operation
    with pytest.raises(CleaningStateError, match="Only ACTIVE operations can be stopped"):
        tracker.stop_operation("OP-100")

    # Cannot complete non-existent operation
    with pytest.raises(CleaningNotFoundError, match="not found"):
        tracker.complete_operation("OP-MISSING")


def test_operation_tracker_failure_flow() -> None:
    tracker = CleaningOperationTracker()
    tracker.start_operation("OP-FAIL", "MIS-FAIL")

    failed = tracker.fail_operation("OP-FAIL", reason="Hardware jam")
    assert failed.status == CleaningStatus.FAILED.value

    # Cannot fail already failed operation
    with pytest.raises(CleaningStateError, match="terminal state"):
        tracker.fail_operation("OP-FAIL")


def test_effectiveness_evaluation_successful_cleaning() -> None:
    # Mission MIS-EFF: Before has 3 defects, After has 1 defect in target range [10m, 20m]
    meta_before1 = InspectionFrameMetadata("MIS-EFF", 1, distance_m=12.0)
    meta_before2 = InspectionFrameMetadata("MIS-EFF", 2, distance_m=15.0)
    meta_before3 = InspectionFrameMetadata("MIS-EFF", 3, distance_m=18.0)

    fused_b1 = fuse_observations(RawPerceptionItem("deposit", 0.8, "yolo"), meta_before1)[0]
    fused_b2 = fuse_observations(RawPerceptionItem("roots", 0.85, "yolo"), meta_before2)[0]
    fused_b3 = fuse_observations(RawPerceptionItem("deposit", 0.9, "yolo"), meta_before3)[0]

    # After cleaning: deposit cleared, only roots remains
    meta_after1 = InspectionFrameMetadata("MIS-EFF", 4, distance_m=15.0)
    fused_a1 = fuse_observations(RawPerceptionItem("roots", 0.82, "yolo"), meta_after1)[0]

    op = CleaningOperation(
        operation_id="CLEAN-EFF",
        mission_id="MIS-EFF",
        mode=CleaningMode.FLUSH.value,
        status=CleaningStatus.COMPLETED.value,
        start_timestamp=datetime.now(timezone.utc),
        end_timestamp=datetime.now(timezone.utc),
        start_distance_m=10.0,
        end_distance_m=20.0,
    )

    result = evaluate_cleaning_effectiveness(op, [fused_b1, fused_b2, fused_b3], [fused_a1])

    assert isinstance(result, CleaningEffectiveness)
    assert result.is_effective is True
    assert result.before_observation_count == 3
    assert result.after_observation_count == 1
    assert "deposit" in result.resolved_defect_classes
    assert "roots" in result.persistent_defect_classes
    assert len(result.new_defect_classes) == 0
    assert result.confidence == "HIGH"


def test_effectiveness_evaluation_incompatible_datasets() -> None:
    op = CleaningOperation(
        operation_id="CLEAN-INCOMPAT",
        mission_id="MIS-MAIN",
        mode=CleaningMode.FLUSH.value,
        status=CleaningStatus.COMPLETED.value,
        start_timestamp=None,
        end_timestamp=None,
        start_distance_m=5.0,
        end_distance_m=15.0,
    )

    # Before dataset from different mission
    meta1 = InspectionFrameMetadata("MIS-DIFF", 1, distance_m=10.0)
    fused_b = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo"), meta1)[0]

    meta2 = InspectionFrameMetadata("MIS-MAIN", 1, distance_m=10.0)
    fused_a = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo"), meta2)[0]

    result = evaluate_cleaning_effectiveness(op, [fused_b], [fused_a], require_same_mission=True)

    assert result.confidence == "UNAVAILABLE"
    assert result.is_effective is None
    assert len(result.unavailable_reasons) > 0
    assert "does not match cleaning operation mission" in result.unavailable_reasons[0]


def test_effectiveness_evaluation_no_overlapping_observations() -> None:
    op = CleaningOperation(
        operation_id="CLEAN-SPATIAL",
        mission_id="MIS-SPATIAL",
        mode=CleaningMode.FLUSH.value,
        status=CleaningStatus.COMPLETED.value,
        start_timestamp=None,
        end_timestamp=None,
        start_distance_m=50.0,
        end_distance_m=60.0,
    )

    # Observations at distance 5m, far outside 50-60m range
    meta = InspectionFrameMetadata("MIS-SPATIAL", 1, distance_m=5.0)
    fused = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo"), meta)[0]

    result = evaluate_cleaning_effectiveness(op, [fused], [fused])

    assert result.confidence == "UNAVAILABLE"
    assert result.is_effective is None
    assert "No valid observations found" in result.unavailable_reasons[0]


def test_end_to_end_robot_controller_cleaning_pipeline() -> None:
    sim = SimulatorTransport(robot_id="PV-CLEAN-SIM", mission_id="MIS-E2E")
    ctrl = RobotController(sim)
    ctrl.connect()

    tracker = CleaningOperationTracker()

    # 1. Start cleaning via controller + tracker
    op = tracker.start_operation(
        operation_id="OP-E2E",
        mission_id="MIS-E2E",
        mode=CleaningMode.FLUSH.value,
        start_distance_m=2.0,
        controller=ctrl,  # Will invoke ctrl.clean_start("FLUSH")
    )
    assert op.status == CleaningStatus.ACTIVE.value

    # 2. Stop cleaning via controller + tracker
    stopped_op = tracker.stop_operation(
        operation_id="OP-E2E",
        end_distance_m=10.0,
        controller=ctrl,  # Will invoke ctrl.clean_stop()
    )
    assert stopped_op.status == CleaningStatus.STOPPED.value

    # 3. Create before & after map observations
    meta_before1 = InspectionFrameMetadata("MIS-E2E", 1, distance_m=3.0)
    meta_before2 = InspectionFrameMetadata("MIS-E2E", 2, distance_m=7.0)
    fused_b1 = fuse_observations(RawPerceptionItem("sediment", 0.9, "yolo"), meta_before1)[0]
    fused_b2 = fuse_observations(RawPerceptionItem("sediment", 0.85, "yolo"), meta_before2)[0]
    before_map = build_inspection_map([fused_b1, fused_b2])

    meta_after1 = InspectionFrameMetadata("MIS-E2E", 3, distance_m=7.0)
    fused_a1 = fuse_observations(RawPerceptionItem("sediment", 0.4, "yolo"), meta_after1)[0]
    after_map = build_inspection_map([fused_a1])

    # 4. Evaluate effectiveness
    eff = evaluate_cleaning_effectiveness(stopped_op, before_map, after_map)

    assert eff.operation_id == "OP-E2E"
    assert eff.is_effective is True
    assert eff.before_observation_count == 2
    assert eff.after_observation_count == 1

    ctrl.disconnect()
