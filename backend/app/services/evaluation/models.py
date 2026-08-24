"""Typed Ground-Truth Contracts, Error Taxonomy, and Evaluation Result Models.

Provides authoritative data structures for ground-truth representation, diagnostic error
categorization, statistical support tracking, and reproducible evaluation reporting across
the PipeVision perception, localization, morphology, and mission orchestrator domains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from backend.app.services.inspection.models import BoundingBox


class ErrorTaxonomy(str, Enum):
    """Explicit diagnostic error categories for PipeVision evaluation."""

    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"
    CLASS_MISMATCH = "CLASS_MISMATCH"
    LOCATION_ERROR = "LOCATION_ERROR"
    MORPHOLOGY_ERROR = "MORPHOLOGY_ERROR"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    INFERENCE_FAILURE = "INFERENCE_FAILURE"
    INVALID_GROUND_TRUTH = "INVALID_GROUND_TRUTH"


class MetricAvailability(str, Enum):
    """Status indicator for metric calculation availability."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"
    UNCALIBRATED = "UNCALIBRATED"


@dataclass(frozen=True)
class GroundTruthDefect:
    """Ground truth defect instance within a frame or pipe location.

    Documentation of source:
    - class_code: Defect code (e.g., 'CR', 'RB', 'OB') from trusted annotation.
    - box: 2D pixel bounding box when box annotation exists (otherwise None).
    - confidence_independent: True because ground-truth is label truth, independent of model scores.
    """

    class_code: str
    box: BoundingBox | None = None
    confidence_independent: bool = True
    severity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_code": self.class_code,
            "box": self.box.to_dict() if self.box is not None else None,
            "confidence_independent": self.confidence_independent,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class GroundTruthFrame:
    """Typed ground-truth contract for an individual inspected image or video frame.

    Documentation of ground-truth sources:
    - frame_id: Unique identity matching mission/frame metadata.
    - filename: Image file name (e.g. '00007027.png' in Sewer-ML).
    - defects: List of verified defect instances with optional bounding boxes.
    - presence: Multi-label mapping {class_code: bool} indicating defect presence.
    - true_distance_m: Reference longitudinal distance from trusted encoder/laser benchmark.
    - true_timestamp: Reference UTC timestamp from trusted clock sync.
    - true_pipe_diameter_mm: Reference physical inner diameter from calibrated caliper/laser.
    - true_deformation_percent: Reference pipe cross-section reduction percentage.
    - source: Provenance descriptor of the reference annotation dataset.
    """

    frame_id: str
    filename: str | None = None
    frame_index: int | None = None
    defects: list[GroundTruthDefect] = field(default_factory=list)
    presence: dict[str, bool] = field(default_factory=dict)
    true_distance_m: float | None = None
    true_timestamp: str | datetime | None = None
    true_pipe_diameter_mm: float | None = None
    true_deformation_percent: float | None = None
    source: str = "curated_annotation"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "filename": self.filename,
            "frame_index": self.frame_index,
            "defects": [d.to_dict() for d in self.defects],
            "presence": self.presence,
            "true_distance_m": self.true_distance_m,
            "true_timestamp": (
                self.true_timestamp.isoformat()
                if isinstance(self.true_timestamp, datetime)
                else self.true_timestamp
            ),
            "true_pipe_diameter_mm": self.true_pipe_diameter_mm,
            "true_deformation_percent": self.true_deformation_percent,
            "source": self.source,
        }


@dataclass(frozen=True)
class GroundTruthMission:
    """Typed ground-truth contract for an entire inspection mission sequence."""

    mission_id: str
    frames: list[GroundTruthFrame]
    true_pipe_length_m: float | None = None
    source: str = "curated_mission_dataset"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "total_frames": len(self.frames),
            "true_pipe_length_m": self.true_pipe_length_m,
            "source": self.source,
            "frames": [f.to_dict() for f in self.frames],
        }


@dataclass(frozen=True)
class ClassMetricSummary:
    """Per-class metric calculations with statistical support bounds."""

    class_code: str
    precision: float
    recall: float
    f1: float
    support: int  # Number of positive ground-truth instances
    negative_support: int  # Number of negative ground-truth instances
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    status: MetricAvailability = MetricAvailability.AVAILABLE
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_code": self.class_code,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "support": self.support,
            "negative_support": self.negative_support,
            "confusion_matrix": {
                "tp": self.true_positives,
                "fp": self.false_positives,
                "fn": self.false_negatives,
                "tn": self.true_negatives,
            },
            "status": self.status.value,
            "note": self.note,
        }


@dataclass(frozen=True)
class DetectionMetricsReport:
    """2D Bounding Box detection metrics evaluated via IoU matching."""

    status: MetricAvailability
    iou_threshold: float
    total_evaluated_frames: int
    total_ground_truth_boxes: int
    total_predicted_boxes: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    per_class_metrics: dict[str, ClassMetricSummary] = field(default_factory=dict)
    reason_if_unavailable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "iou_threshold": self.iou_threshold,
            "total_evaluated_frames": self.total_evaluated_frames,
            "total_ground_truth_boxes": self.total_ground_truth_boxes,
            "total_predicted_boxes": self.total_predicted_boxes,
            "overall": {
                "true_positives": self.true_positives,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1": round(self.f1, 4),
            },
            "per_class": {cls: summary.to_dict() for cls, summary in self.per_class_metrics.items()},
            "reason_if_unavailable": self.reason_if_unavailable,
        }


@dataclass(frozen=True)
class ClassificationMetricsReport:
    """Multi-label image/frame defect classification performance report."""

    status: MetricAvailability
    total_evaluated_frames: int
    macro_precision: float
    macro_recall: float
    macro_f1: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    exact_match_ratio: float  # Subset accuracy for multi-label
    per_class_metrics: dict[str, ClassMetricSummary] = field(default_factory=dict)
    reason_if_unavailable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "total_evaluated_frames": self.total_evaluated_frames,
            "macro": {
                "precision": round(self.macro_precision, 4),
                "recall": round(self.macro_recall, 4),
                "f1": round(self.macro_f1, 4),
            },
            "micro": {
                "precision": round(self.micro_precision, 4),
                "recall": round(self.micro_recall, 4),
                "f1": round(self.micro_f1, 4),
            },
            "exact_match_ratio": round(self.exact_match_ratio, 4),
            "per_class": {cls: summary.to_dict() for cls, summary in self.per_class_metrics.items()},
            "reason_if_unavailable": self.reason_if_unavailable,
        }


@dataclass(frozen=True)
class CalibrationBin:
    """Confidence calibration bin metrics."""

    bin_lower: float
    bin_upper: float
    sample_count: int
    avg_confidence: float
    empirical_accuracy: float


@dataclass(frozen=True)
class CalibrationReport:
    """Confidence calibration metrics (ECE and reliability diagram analysis)."""

    status: MetricAvailability
    sample_count: int
    expected_calibration_error: float | None = None
    bins: list[CalibrationBin] = field(default_factory=list)
    reason_if_unavailable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "sample_count": self.sample_count,
            "expected_calibration_error": (
                round(self.expected_calibration_error, 4)
                if self.expected_calibration_error is not None
                else None
            ),
            "bins": [
                {
                    "bin_range": [round(b.bin_lower, 2), round(b.bin_upper, 2)],
                    "sample_count": b.sample_count,
                    "avg_confidence": round(b.avg_confidence, 4),
                    "empirical_accuracy": round(b.empirical_accuracy, 4),
                }
                for b in self.bins
            ],
            "reason_if_unavailable": self.reason_if_unavailable,
        }


@dataclass(frozen=True)
class LocalizationMetricsReport:
    """Longitudinal position and robot pose error evaluation."""

    status: MetricAvailability
    sample_count: int
    mean_absolute_error_m: float | None = None
    median_absolute_error_m: float | None = None
    max_absolute_error_m: float | None = None
    p95_absolute_error_m: float | None = None
    reason_if_unavailable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "sample_count": self.sample_count,
            "mean_absolute_error_m": (
                round(self.mean_absolute_error_m, 4)
                if self.mean_absolute_error_m is not None
                else None
            ),
            "median_absolute_error_m": (
                round(self.median_absolute_error_m, 4)
                if self.median_absolute_error_m is not None
                else None
            ),
            "max_absolute_error_m": (
                round(self.max_absolute_error_m, 4)
                if self.max_absolute_error_m is not None
                else None
            ),
            "p95_absolute_error_m": (
                round(self.p95_absolute_error_m, 4)
                if self.p95_absolute_error_m is not None
                else None
            ),
            "reason_if_unavailable": self.reason_if_unavailable,
        }


@dataclass(frozen=True)
class MorphologyMetricsReport:
    """Pipe geometry and deformation measurement accuracy report."""

    status: MetricAvailability
    sample_count: int
    mean_diameter_error_mm: float | None = None
    median_diameter_error_mm: float | None = None
    mean_relative_diameter_error_percent: float | None = None
    mean_deformation_error_percent: float | None = None
    calibration_status: str = "UNCALIBRATED"
    reason_if_unavailable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "sample_count": self.sample_count,
            "calibration_status": self.calibration_status,
            "mean_diameter_error_mm": (
                round(self.mean_diameter_error_mm, 2)
                if self.mean_diameter_error_mm is not None
                else None
            ),
            "median_diameter_error_mm": (
                round(self.median_diameter_error_mm, 2)
                if self.median_diameter_error_mm is not None
                else None
            ),
            "mean_relative_diameter_error_percent": (
                round(self.mean_relative_diameter_error_percent, 2)
                if self.mean_relative_diameter_error_percent is not None
                else None
            ),
            "mean_deformation_error_percent": (
                round(self.mean_deformation_error_percent, 2)
                if self.mean_deformation_error_percent is not None
                else None
            ),
            "reason_if_unavailable": self.reason_if_unavailable,
        }


@dataclass(frozen=True)
class DefectLocationMetricsReport:
    """Longitudinal defect location accuracy matching predicted defects to ground truth spatial locations."""

    status: MetricAvailability
    matched_defects_count: int
    unmatched_predicted_count: int
    unmatched_ground_truth_count: int
    mean_spatial_error_m: float | None = None
    max_spatial_error_m: float | None = None
    distance_tolerance_m: float = 1.0
    reason_if_unavailable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "distance_tolerance_m": self.distance_tolerance_m,
            "matched_defects_count": self.matched_defects_count,
            "unmatched_predicted_count": self.unmatched_predicted_count,
            "unmatched_ground_truth_count": self.unmatched_ground_truth_count,
            "mean_spatial_error_m": (
                round(self.mean_spatial_error_m, 3)
                if self.mean_spatial_error_m is not None
                else None
            ),
            "max_spatial_error_m": (
                round(self.max_spatial_error_m, 3)
                if self.max_spatial_error_m is not None
                else None
            ),
            "reason_if_unavailable": self.reason_if_unavailable,
        }


@dataclass(frozen=True)
class MissionEvaluationReport:
    """Comprehensive, fully reproducible evaluation report for a PipeVision inspection session."""

    evaluation_version: str
    dataset_source: str
    model_name: str
    model_version: str
    eval_timestamp_iso: str
    total_frames: int
    analyzed_frames: int
    failed_frames: int
    detection: DetectionMetricsReport
    classification: ClassificationMetricsReport
    calibration: CalibrationReport
    localization: LocalizationMetricsReport
    morphology: MorphologyMetricsReport
    defect_location: DefectLocationMetricsReport
    error_taxonomy_counts: dict[str, int]
    random_seed: int = 42

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "evaluation_version": self.evaluation_version,
                "dataset_source": self.dataset_source,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "eval_timestamp": self.eval_timestamp_iso,
                "random_seed": self.random_seed,
            },
            "summary_counts": {
                "total_frames": self.total_frames,
                "analyzed_frames": self.analyzed_frames,
                "failed_frames": self.failed_frames,
            },
            "error_taxonomy": self.error_taxonomy_counts,
            "detection": self.detection.to_dict(),
            "classification": self.classification.to_dict(),
            "calibration": self.calibration.to_dict(),
            "localization": self.localization.to_dict(),
            "morphology": self.morphology.to_dict(),
            "defect_location": self.defect_location.to_dict(),
        }
