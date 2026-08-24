"""PipeVision Accuracy and Ground-Truth Evaluation Service Package."""

from backend.app.services.evaluation.adapters import (
    GenericAnnotationAdapter,
    SewerMLAnnotationAdapter,
)
from backend.app.services.evaluation.evaluator import (
    PipeVisionEvaluator,
    calculate_iou,
)
from backend.app.services.evaluation.models import (
    CalibrationBin,
    CalibrationReport,
    ClassificationMetricsReport,
    ClassMetricSummary,
    DefectLocationMetricsReport,
    DetectionMetricsReport,
    ErrorTaxonomy,
    GroundTruthDefect,
    GroundTruthFrame,
    GroundTruthMission,
    LocalizationMetricsReport,
    MetricAvailability,
    MissionEvaluationReport,
    MorphologyMetricsReport,
)

__all__ = [
    "CalibrationBin",
    "CalibrationReport",
    "ClassMetricSummary",
    "ClassificationMetricsReport",
    "DefectLocationMetricsReport",
    "DetectionMetricsReport",
    "ErrorTaxonomy",
    "GenericAnnotationAdapter",
    "GroundTruthDefect",
    "GroundTruthFrame",
    "GroundTruthMission",
    "LocalizationMetricsReport",
    "MetricAvailability",
    "MissionEvaluationReport",
    "MorphologyMetricsReport",
    "PipeVisionEvaluator",
    "SewerMLAnnotationAdapter",
    "calculate_iou",
]
