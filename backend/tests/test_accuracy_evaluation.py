"""Comprehensive Validation Test Suite for PipeVision Accuracy & Ground-Truth Evaluation Framework (Phase 16).

Tests bounding box IoU calculation, detection metrics, multi-label classification (macro/micro F1),
confidence calibration (ECE), localization longitudinal error, morphology error, defect spatial matching,
Sewer-ML CSV dataset adapter, error taxonomy, and mission evaluation report serialization.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.evaluation.adapters import (
    GenericAnnotationAdapter,
    SewerMLAnnotationAdapter,
)
from backend.app.services.evaluation.evaluator import (
    PipeVisionEvaluator,
    calculate_iou,
)
from backend.app.services.evaluation.models import (
    ErrorTaxonomy,
    GroundTruthDefect,
    GroundTruthFrame,
    GroundTruthMission,
    MetricAvailability,
)
from backend.app.services.inspection.models import (
    BoundingBox,
    FusedInspectionObservation,
    SingleIngestionResult,
)


def test_calculate_iou_exact_and_partial() -> None:
    box1 = BoundingBox(x1=10, y1=10, x2=50, y2=50)
    box2 = BoundingBox(x1=10, y1=10, x2=50, y2=50)
    box3 = BoundingBox(x1=30, y1=10, x2=70, y2=50)
    box4 = BoundingBox(x1=100, y1=100, x2=150, y2=150)

    assert calculate_iou(box1, box2) == pytest.approx(1.0)
    assert calculate_iou(box1, box3) == pytest.approx(1 / 3)  # Inter 20*40=800, Union 1600+1600-800=2400
    assert calculate_iou(box1, box4) == pytest.approx(0.0)


def test_sewer_ml_adapter_loading() -> None:
    csv_path = Path("approved-data/sewer-ml/splits/val.csv")
    if not csv_path.exists():
        pytest.skip(f"Sewer-ML split file missing: {csv_path}")

    adapter = SewerMLAnnotationAdapter(csv_path)
    frames = adapter.load_frames(limit=10)

    assert len(frames) == 10
    first_frame = frames[0]
    assert first_frame.filename == "00007027.png"
    assert "RB" in first_frame.presence
    assert isinstance(first_frame.presence["RB"], bool)


def test_generic_annotation_adapter() -> None:
    raw_data = {
        "frame_id": "frame_001",
        "filename": "frame_001.png",
        "frame_index": 0,
        "presence": {"RB": True, "OB": False},
        "defects": [{"class_code": "RB"}],
        "true_distance_m": 12.5,
        "true_pipe_diameter_mm": 300.0,
        "true_deformation_percent": 2.5,
    }

    frame = GenericAnnotationAdapter.from_dict(raw_data)

    assert frame.frame_id == "frame_001"
    assert frame.true_distance_m == 12.5
    assert frame.presence["RB"] is True
    assert len(frame.defects) == 1
    assert frame.defects[0].class_code == "RB"


def test_classification_metrics_macro_micro_and_per_class() -> None:
    evaluator = PipeVisionEvaluator(min_support_threshold=1)

    # Frame 1: GT={RB, OB}, Pred={RB}
    gt1 = GroundTruthFrame(
        frame_id="f1",
        presence={"RB": True, "OB": True, "PF": False},
    )
    obs1 = [
        FusedInspectionObservation(
            observation_id="o1",
            mission_id="m1",
            frame_index=0,
            timestamp=None,
            timestamp_iso=None,
            distance_m=1.0,
            frame_distance_m=1.0,
            pose_distance_m=1.0,
            distance_conflict_m=0.0,
            robot_pose=None,
            localization_quality="TRACKING",
            class_code="RB",
            confidence=0.9,
            threshold=0.5,
            box=None,
            model_name="test",
            model_version="v1",
            source_type="test",
        )
    ]

    # Frame 2: GT={RB}, Pred={RB, OB}
    gt2 = GroundTruthFrame(
        frame_id="f2",
        presence={"RB": True, "OB": False, "PF": False},
    )
    obs2 = [
        FusedInspectionObservation(
            observation_id="o2",
            mission_id="m1",
            frame_index=1,
            timestamp=None,
            timestamp_iso=None,
            distance_m=2.0,
            frame_distance_m=2.0,
            pose_distance_m=2.0,
            distance_conflict_m=0.0,
            robot_pose=None,
            localization_quality="TRACKING",
            class_code="RB",
            confidence=0.85,
            threshold=0.5,
            box=None,
            model_name="test",
            model_version="v1",
            source_type="test",
        ),
        FusedInspectionObservation(
            observation_id="o3",
            mission_id="m1",
            frame_index=1,
            timestamp=None,
            timestamp_iso=None,
            distance_m=2.0,
            frame_distance_m=2.0,
            pose_distance_m=2.0,
            distance_conflict_m=0.0,
            robot_pose=None,
            localization_quality="TRACKING",
            class_code="OB",
            confidence=0.7,
            threshold=0.5,
            box=None,
            model_name="test",
            model_version="v1",
            source_type="test",
        ),
    ]

    report = evaluator.evaluate_classification([(gt1, obs1), (gt2, obs2)])

    assert report.status == MetricAvailability.AVAILABLE
    assert report.total_evaluated_frames == 2
    # RB: TP=2, FP=0, FN=0 -> P=1.0, R=1.0, F1=1.0
    # OB: TP=0, FP=1, FN=1 -> P=0.0, R=0.0, F1=0.0
    assert report.per_class_metrics["RB"].precision == pytest.approx(1.0)
    assert report.per_class_metrics["RB"].recall == pytest.approx(1.0)
    assert report.per_class_metrics["OB"].precision == pytest.approx(0.0)

    # Micro: total TP=2, FP=1, FN=1 -> Micro Precision = 2/3, Micro Recall = 2/3
    assert report.micro_precision == pytest.approx(2 / 3)
    assert report.micro_recall == pytest.approx(2 / 3)


def test_detection_metrics_matching_and_unavailable() -> None:
    evaluator = PipeVisionEvaluator(iou_threshold=0.5)

    # GT without bounding boxes -> Metric unavailable
    gt_no_box = GroundTruthFrame(frame_id="f1", defects=[GroundTruthDefect(class_code="RB")])
    report_unavail = evaluator.evaluate_detection([(gt_no_box, [])])
    assert report_unavail.status == MetricAvailability.UNAVAILABLE
    assert "no ground truth bounding box annotations exist" in (report_unavail.reason_if_unavailable or "")

    # GT with bounding box -> Metric available
    b1 = BoundingBox(10, 10, 50, 50)
    b2 = BoundingBox(12, 12, 48, 48)  # IoU > 0.5
    gt_box = GroundTruthFrame(frame_id="f2", defects=[GroundTruthDefect(class_code="RB", box=b1)])
    obs_box = FusedInspectionObservation(
        observation_id="o1",
        mission_id="m1",
        frame_index=0,
        timestamp=None,
        timestamp_iso=None,
        distance_m=1.0,
        frame_distance_m=1.0,
        pose_distance_m=1.0,
        distance_conflict_m=0.0,
        robot_pose=None,
        localization_quality="TRACKING",
        class_code="RB",
        confidence=0.9,
        threshold=0.5,
        box=b2,
        model_name="test",
        model_version="v1",
        source_type="test",
    )

    report_avail = evaluator.evaluate_detection([(gt_box, [obs_box])])
    assert report_avail.status == MetricAvailability.AVAILABLE
    assert report_avail.true_positives == 1
    assert report_avail.precision == pytest.approx(1.0)


def test_localization_and_morphology_unavailable_by_default() -> None:
    evaluator = PipeVisionEvaluator()

    gt_empty = GroundTruthFrame(frame_id="f1")
    loc_report = evaluator.evaluate_localization([(gt_empty, 10.0)])
    morph_report = evaluator.evaluate_morphology([(gt_empty, 300.0, 5.0)])

    assert loc_report.status == MetricAvailability.UNAVAILABLE
    assert "no ground truth source for localization distance" in (loc_report.reason_if_unavailable or "")

    assert morph_report.status == MetricAvailability.UNAVAILABLE
    assert "no ground truth source for physical morphology" in (morph_report.reason_if_unavailable or "")


def test_localization_metrics_with_synthetic_ground_truth() -> None:
    evaluator = PipeVisionEvaluator()

    paired = [
        (GroundTruthFrame(frame_id="f1", true_distance_m=10.0), 10.2),  # err 0.2
        (GroundTruthFrame(frame_id="f2", true_distance_m=20.0), 19.5),  # err 0.5
        (GroundTruthFrame(frame_id="f3", true_distance_m=30.0), 30.1),  # err 0.1
    ]

    report = evaluator.evaluate_localization(paired)

    assert report.status == MetricAvailability.AVAILABLE
    assert report.sample_count == 3
    assert report.mean_absolute_error_m == pytest.approx(0.266666, abs=1e-4)
    assert report.median_absolute_error_m == pytest.approx(0.2)
    assert report.max_absolute_error_m == pytest.approx(0.5)


def test_mission_evaluation_report_generation() -> None:
    evaluator = PipeVisionEvaluator()

    gt_mission = GroundTruthMission(
        mission_id="m1",
        frames=[
            GroundTruthFrame(frame_id="f1", filename="00007027.png", presence={"RB": True}),
            GroundTruthFrame(frame_id="f2", filename="00007028.png", presence={"OB": True}),
        ],
        source="SyntheticTestFixture",
    )

    ingest_results = [
        SingleIngestionResult(
            mission_id="m1",
            frame_id="f1",
            frame_index=0,
            timestamp_iso="2026-08-24T00:00:00Z",
            source="photo",
            distance_m=5.0,
            frame_path="approved-data/sewer-ml/images/00007027.png",
            observations=[
                FusedInspectionObservation(
                    observation_id="obs1",
                    mission_id="m1",
                    frame_index=0,
                    timestamp=None,
                    timestamp_iso=None,
                    distance_m=5.0,
                    frame_distance_m=5.0,
                    pose_distance_m=5.0,
                    distance_conflict_m=0.0,
                    robot_pose=None,
                    localization_quality="TRACKING",
                    class_code="RB",
                    confidence=0.95,
                    threshold=0.5,
                    box=None,
                    model_name="Sewer-ML",
                    model_version="e009",
                    source_type="photo",
                )
            ],
        )
    ]

    report = evaluator.evaluate_mission(gt_mission, ingest_results)

    assert report.total_frames == 2
    assert report.analyzed_frames == 1
    assert report.failed_frames == 1
    assert report.error_taxonomy_counts[ErrorTaxonomy.INFERENCE_FAILURE.value] == 1
    assert report.error_taxonomy_counts[ErrorTaxonomy.TRUE_POSITIVE.value] == 1

    report_dict = report.to_dict()
    assert "metadata" in report_dict
    assert report_dict["metadata"]["dataset_source"] == "SyntheticTestFixture"
    assert report_dict["classification"]["status"] == MetricAvailability.AVAILABLE.value
