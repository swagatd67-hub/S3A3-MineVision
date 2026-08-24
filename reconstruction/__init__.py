"""PipeVision 3D Pipe Reconstruction Domain Module."""

from __future__ import annotations

from reconstruction.analysis_models import (
    Defect3DMeasurement,
    Deformation3DMetrics,
    HeatmapProfile3D,
    MetricAvailabilityStatus,
    Pipe3DAnalysisReport,
    Pipe3DConditionSummary,
    PipeSection3DCondition,
    SpatialRelationship3D,
)
from reconstruction.condition_analyzer import Pipe3DConditionAnalyzer
from reconstruction.defect_extent import (
    compute_defect_extent,
    compute_spatial_relationships,
)
from reconstruction.deformation_analyzer import analyze_pipe_deformation
from reconstruction.exceptions import (
    CalibrationError,
    CoordinateTransformError,
    InsufficientDataError,
    ReconstructionError,
    ScaleEstimationError,
)
from reconstruction.models import (
    CameraCalibration,
    PipeCenterline,
    PipeCenterlinePoint,
    PipeSurfacePoint,
    Point3D,
    Reconstruction3DOutput,
    ReconstructionFrame,
    ReconstructionJob,
    ReconstructionMethod,
    ReconstructionQualityState,
    ScaleStatus,
)
from reconstruction.synthetic_analysis_scene import SyntheticAnalysisSceneGenerator

__all__ = [
    "CalibrationError",
    "CameraCalibration",
    "CoordinateTransformError",
    "Defect3DMeasurement",
    "Deformation3DMetrics",
    "HeatmapProfile3D",
    "InsufficientDataError",
    "MetricAvailabilityStatus",
    "Pipe3DAnalysisReport",
    "Pipe3DConditionAnalyzer",
    "Pipe3DConditionSummary",
    "PipeCenterline",
    "PipeCenterlinePoint",
    "PipeSection3DCondition",
    "PipeSurfacePoint",
    "Point3D",
    "Reconstruction3DOutput",
    "ReconstructionError",
    "ReconstructionFrame",
    "ReconstructionJob",
    "ReconstructionMethod",
    "ReconstructionQualityState",
    "ScaleEstimationError",
    "ScaleStatus",
    "SpatialRelationship3D",
    "SyntheticAnalysisSceneGenerator",
    "analyze_pipe_deformation",
    "compute_defect_extent",
    "compute_spatial_relationships",
]
