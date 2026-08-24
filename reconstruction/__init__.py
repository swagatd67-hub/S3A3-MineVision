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
from reconstruction.graph_analytics import (
    calculate_edge_priority_score,
    compute_network_connectivity,
    generate_network_analytics,
)
from reconstruction.graph_builder import PipeNetworkGraphBuilder
from reconstruction.graph_integration import (
    associate_graph_with_digital_twin,
    associate_graph_with_mapping,
)
from reconstruction.graph_models import (
    DefectOnEdge,
    DefectOwnershipStatus,
    FlowDirection,
    GraphEdge,
    GraphNode,
    GraphQualityState,
    NetworkAnalyticsSummary,
    NetworkConnectivityMetrics,
    NodeType,
    PipeNetworkGraph,
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
from reconstruction.synthetic_graph_scene import SyntheticGraphSceneGenerator

__all__ = [
    "CalibrationError",
    "CameraCalibration",
    "CoordinateTransformError",
    "Defect3DMeasurement",
    "DefectOnEdge",
    "DefectOwnershipStatus",
    "Deformation3DMetrics",
    "FlowDirection",
    "GraphEdge",
    "GraphNode",
    "GraphQualityState",
    "HeatmapProfile3D",
    "InsufficientDataError",
    "MetricAvailabilityStatus",
    "NetworkAnalyticsSummary",
    "NetworkConnectivityMetrics",
    "NodeType",
    "Pipe3DAnalysisReport",
    "Pipe3DConditionAnalyzer",
    "Pipe3DConditionSummary",
    "PipeCenterline",
    "PipeCenterlinePoint",
    "PipeNetworkGraph",
    "PipeNetworkGraphBuilder",
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
    "SyntheticGraphSceneGenerator",
    "analyze_pipe_deformation",
    "associate_graph_with_digital_twin",
    "associate_graph_with_mapping",
    "calculate_edge_priority_score",
    "compute_defect_extent",
    "compute_network_connectivity",
    "compute_spatial_relationships",
    "generate_network_analytics",
]
