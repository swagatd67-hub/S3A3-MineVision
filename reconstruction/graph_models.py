"""Domain Models for Phase 26 Graph Reconstruction and Network Analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from reconstruction.models import Point3D, ScaleStatus


class NodeType(str, Enum):
    """Supported pipe network node classifications."""

    MANHOLE = "MANHOLE"
    JUNCTION = "JUNCTION"
    PIPE_ENDPOINT = "PIPE_ENDPOINT"
    INSPECTION_REFERENCE = "INSPECTION_REFERENCE"
    UNKNOWN = "UNKNOWN"


class FlowDirection(str, Enum):
    """Pipe flow or traversal direction relative to graph topology."""

    UPSTREAM_TO_DOWNSTREAM = "UPSTREAM_TO_DOWNSTREAM"
    DOWNSTREAM_TO_UPSTREAM = "DOWNSTREAM_TO_UPSTREAM"
    BIDIRECTIONAL = "BIDIRECTIONAL"
    UNKNOWN = "UNKNOWN"


class GraphQualityState(str, Enum):
    """Quality state of the reconstructed network graph or edge segment."""

    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class DefectOwnershipStatus(str, Enum):
    """Status of projected 3D defect association with a specific graph edge."""

    UNIQUE_OWNER = "UNIQUE_OWNER"
    AMBIGUOUS = "AMBIGUOUS"
    UNASSOCIATED = "UNASSOCIATED"


@dataclass(frozen=True)
class DefectOnEdge:
    """Lightweight reference to a projected 3D defect associated with a graph edge segment."""

    projection_id: str
    observation_id: str
    class_code: str
    longitudinal_s_m: float
    angular_theta_rad: float | None
    ownership_status: DefectOwnershipStatus
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert defect-on-edge reference to standard dictionary format."""
        return {
            "projection_id": self.projection_id,
            "observation_id": self.observation_id,
            "class_code": self.class_code,
            "longitudinal_s_m": round(self.longitudinal_s_m, 3),
            "angular_theta_rad": (
                round(self.angular_theta_rad, 4)
                if self.angular_theta_rad is not None
                else None
            ),
            "ownership_status": self.ownership_status.value,
            "confidence": round(self.confidence, 4),
        }


@dataclass(frozen=True)
class GraphNode:
    """Immutable vertex in the pipe network graph representation."""

    node_id: str
    node_type: NodeType
    position_3d: Point3D | None
    longitudinal_s_m: float | None
    label: str
    provenance_source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert graph node to dictionary format for serialization and frontend consumption."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "position_3d": self.position_3d.to_dict() if self.position_3d is not None else None,
            "longitudinal_s_m": (
                round(self.longitudinal_s_m, 3)
                if self.longitudinal_s_m is not None
                else None
            ),
            "label": self.label,
            "provenance_source": self.provenance_source,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class GraphEdge:
    """Immutable edge representing a pipe segment connecting two network nodes."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    length_m: float
    diameter_mm: float
    flow_direction: FlowDirection
    reconstruction_id: str | None
    scale_status: ScaleStatus
    quality_state: GraphQualityState
    defects: tuple[DefectOnEdge, ...] = ()
    defect_count: int = 0
    defect_density_per_m: float = 0.0
    max_deformation_percent: float | None = None
    condition_score: float | None = None
    score_classification: str = "DERIVED_HEURISTIC_CONDITION_SCORE"
    priority_score: float | None = None
    priority_classification: str = "DERIVED_HEURISTIC_PRIORITY"
    quality_notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert graph edge to dictionary format for serialization and frontend consumption."""
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "length_m": round(self.length_m, 3),
            "diameter_mm": round(self.diameter_mm, 1),
            "flow_direction": self.flow_direction.value,
            "reconstruction_id": self.reconstruction_id,
            "scale_status": self.scale_status.value,
            "quality_state": self.quality_state.value,
            "defect_count": self.defect_count,
            "defect_density_per_m": round(self.defect_density_per_m, 4),
            "max_deformation_percent": (
                round(self.max_deformation_percent, 2)
                if self.max_deformation_percent is not None
                else None
            ),
            "condition_score": (
                round(self.condition_score, 2)
                if self.condition_score is not None
                else None
            ),
            "score_classification": self.score_classification,
            "priority_score": (
                round(self.priority_score, 2)
                if self.priority_score is not None
                else None
            ),
            "priority_classification": self.priority_classification,
            "defects": [d.to_dict() for d in self.defects],
            "quality_notes": list(self.quality_notes),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NetworkConnectivityMetrics:
    """Topological graph structure and connectivity diagnostic metrics."""

    total_nodes: int
    total_edges: int
    node_degrees: dict[str, int]
    connected_components_count: int
    component_node_lists: tuple[tuple[str, ...], ...]
    isolated_node_ids: tuple[str, ...]
    dangling_endpoint_ids: tuple[str, ...]
    parallel_edge_count: int
    self_loop_count: int
    disconnected_segment_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert connectivity metrics to dictionary format."""
        return {
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "node_degrees": dict(self.node_degrees),
            "connected_components_count": self.connected_components_count,
            "component_node_lists": [list(c) for c in self.component_node_lists],
            "isolated_node_ids": list(self.isolated_node_ids),
            "dangling_endpoint_ids": list(self.dangling_endpoint_ids),
            "parallel_edge_count": self.parallel_edge_count,
            "self_loop_count": self.self_loop_count,
            "disconnected_segment_count": self.disconnected_segment_count,
        }


@dataclass(frozen=True)
class NetworkAnalyticsSummary:
    """Network-level aggregated statistics, condition distributions, and priority rankings."""

    network_id: str
    total_network_length_m: float
    inspected_network_length_m: float
    inspected_coverage_percent: float
    total_defects: int
    mean_defect_density_per_m: float
    overall_network_condition_score: float | None
    high_defect_edge_ids: tuple[str, ...]
    high_priority_edge_ids: tuple[str, ...]
    connectivity_metrics: NetworkConnectivityMetrics
    analytics_version: str = "Phase26_v1"
    priority_scoring_version: str = "Heuristic_Priority_v1"
    priority_classification: str = "DERIVED_HEURISTIC_PRIORITY"

    def to_dict(self) -> dict[str, Any]:
        """Convert network analytics summary to dictionary format."""
        return {
            "network_id": self.network_id,
            "total_network_length_m": round(self.total_network_length_m, 3),
            "inspected_network_length_m": round(self.inspected_network_length_m, 3),
            "inspected_coverage_percent": round(self.inspected_coverage_percent, 2),
            "total_defects": self.total_defects,
            "mean_defect_density_per_m": round(self.mean_defect_density_per_m, 4),
            "overall_network_condition_score": (
                round(self.overall_network_condition_score, 2)
                if self.overall_network_condition_score is not None
                else None
            ),
            "high_defect_edge_ids": list(self.high_defect_edge_ids),
            "high_priority_edge_ids": list(self.high_priority_edge_ids),
            "connectivity": self.connectivity_metrics.to_dict(),
            "analytics_version": self.analytics_version,
            "priority_scoring_version": self.priority_scoring_version,
            "priority_classification": self.priority_classification,
        }


@dataclass(frozen=True)
class PipeNetworkGraph:
    """Master Pipe Network Graph model representing reconstructed pipe topology and analytics."""

    graph_id: str
    network_id: str
    mission_id: str | None
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    scale_status: ScaleStatus
    quality_state: GraphQualityState
    analytics: NetworkAnalyticsSummary | None = None
    graph_version: str = "Phase26_v1"
    coordinate_frame: str = "LOCAL_INSPECTION_FRAME"
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Convert master pipe network graph to clean machine-readable structure for frontend consumption."""
        return {
            "graph_id": self.graph_id,
            "network_id": self.network_id,
            "mission_id": self.mission_id,
            "graph_version": self.graph_version,
            "coordinate_frame": self.coordinate_frame,
            "scale_status": self.scale_status.value,
            "quality_state": self.quality_state.value,
            "summary": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "total_length_m": (
                    round(sum(e.length_m for e in self.edges), 3) if self.edges else 0.0
                ),
            },
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "analytics": self.analytics.to_dict() if self.analytics is not None else None,
            "limitations": list(self.limitations),
        }
