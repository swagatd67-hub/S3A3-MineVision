"""Synthetic Pipe Network Generator and Ground-Truth Accuracy Evaluator (Phase 26)."""

from __future__ import annotations

from typing import Any

from reconstruction.defect_models import (
    Projected3DDefect,
    ProjectionStatus,
    Source2DGeometry,
)
from reconstruction.graph_builder import PipeNetworkGraphBuilder
from reconstruction.graph_models import (
    FlowDirection,
    GraphNode,
    NodeType,
    PipeNetworkGraph,
)
from reconstruction.models import Point3D, ScaleStatus


class SyntheticGraphSceneGenerator:
    """Generates synthetic pipe network topology with known ground truth for validation and accuracy testing."""

    def __init__(
        self,
        node_count: int = 4,
        edge_length_m: float = 5.0,
        pipe_diameter_mm: float = 300.0,
    ) -> None:
        self.node_count = node_count
        self.edge_length_m = edge_length_m
        self.pipe_diameter_mm = pipe_diameter_mm

    def generate_synthetic_network(self) -> tuple[list[GraphNode], list[dict[str, Any]], list[Projected3DDefect]]:
        """Generate a synthetic 4-node branching pipe network (A->B, B->C, B->D) with 3 known ground-truth defects."""
        # 1. Synthetic Nodes
        nodes = [
            GraphNode(
                node_id="node_A",
                node_type=NodeType.MANHOLE,
                position_3d=Point3D(x=0.0, y=0.0, z=0.0),
                longitudinal_s_m=0.0,
                label="Manhole MH-A",
                provenance_source="SyntheticGroundTruth",
            ),
            GraphNode(
                node_id="node_B",
                node_type=NodeType.JUNCTION,
                position_3d=Point3D(x=5.0, y=0.0, z=0.0),
                longitudinal_s_m=5.0,
                label="Junction J-B",
                provenance_source="SyntheticGroundTruth",
            ),
            GraphNode(
                node_id="node_C",
                node_type=NodeType.MANHOLE,
                position_3d=Point3D(x=10.0, y=0.0, z=0.0),
                longitudinal_s_m=10.0,
                label="Manhole MH-C",
                provenance_source="SyntheticGroundTruth",
            ),
            GraphNode(
                node_id="node_D",
                node_type=NodeType.PIPE_ENDPOINT,
                position_3d=Point3D(x=5.0, y=5.0, z=0.0),
                longitudinal_s_m=10.0,
                label="Endpoint E-D",
                provenance_source="SyntheticGroundTruth",
            ),
        ]

        # 2. Synthetic Edges
        edges = [
            {
                "edge_id": "edge_1_A_to_B",
                "source_node_id": "node_A",
                "target_node_id": "node_B",
                "length_m": self.edge_length_m,
                "diameter_mm": self.pipe_diameter_mm,
                "flow_direction": FlowDirection.UPSTREAM_TO_DOWNSTREAM.value,
                "condition_score": 90.0,
            },
            {
                "edge_id": "edge_2_B_to_C",
                "source_node_id": "node_B",
                "target_node_id": "node_C",
                "length_m": self.edge_length_m,
                "diameter_mm": self.pipe_diameter_mm,
                "flow_direction": FlowDirection.UPSTREAM_TO_DOWNSTREAM.value,
                "condition_score": 75.0,
            },
            {
                "edge_id": "edge_3_B_to_D",
                "source_node_id": "node_B",
                "target_node_id": "node_D",
                "length_m": self.edge_length_m,
                "diameter_mm": self.pipe_diameter_mm,
                "flow_direction": FlowDirection.BIDIRECTIONAL.value,
                "condition_score": 60.0,
            },
        ]

        # 3. Ground-truth defects assigned to edge 1 and edge 2
        src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
        defects = [
            Projected3DDefect(
                projection_id="p_syn_1",
                observation_id="obs_syn_1",
                mission_id="m_syn",
                class_code="CR",
                ai_confidence=0.95,
                projection_confidence=0.90,
                source_2d_geometry=src_geom,
                point_3d=Point3D(x=2.5, y=0.0, z=0.15),
                longitudinal_distance_m=2.5,
                angular_position_rad=0.0,
                radial_position_m=0.15,
                scale_status=ScaleStatus.ESTABLISHED,
                quality_state=ProjectionStatus.VALID,
            ),
            Projected3DDefect(
                projection_id="p_syn_2",
                observation_id="obs_syn_2",
                mission_id="m_syn",
                class_code="BS",
                ai_confidence=0.90,
                projection_confidence=0.88,
                source_2d_geometry=src_geom,
                point_3d=Point3D(x=7.5, y=0.0, z=0.15),
                longitudinal_distance_m=7.5,
                angular_position_rad=0.0,
                radial_position_m=0.15,
                scale_status=ScaleStatus.ESTABLISHED,
                quality_state=ProjectionStatus.VALID,
            ),
        ]

        return nodes, edges, defects

    def evaluate_graph_accuracy(self) -> dict[str, Any]:
        """SYNTHETIC ALGORITHM VALIDATION ONLY: Evaluate graph reconstruction accuracy against synthetic ground truth."""
        nodes, edges, defects = self.generate_synthetic_network()

        builder = PipeNetworkGraphBuilder()
        graph: PipeNetworkGraph = builder.build_graph(
            mission_id="m_syn",
            network_id="net_synthetic_gt",
            defects=defects,
            known_nodes=nodes,
            known_edges=edges,
        )

        gt_node_count = len(nodes)
        gt_edge_count = len(edges)
        gt_total_len = sum(float(e["length_m"]) for e in edges)

        calc_node_count = len(graph.nodes)
        calc_edge_count = len(graph.edges)
        calc_total_len = sum(e.length_m for e in graph.edges)

        node_error = abs(calc_node_count - gt_node_count)
        edge_error = abs(calc_edge_count - gt_edge_count)
        length_error = abs(calc_total_len - gt_total_len)

        # Verify defect-to-edge association accuracy
        e1 = next(e for e in graph.edges if e.edge_id == "edge_1_A_to_B")
        e2 = next(e for e in graph.edges if e.edge_id == "edge_2_B_to_C")

        assoc_correct = (e1.defect_count == 1 and e2.defect_count == 1)
        assoc_accuracy = 100.0 if assoc_correct else 0.0

        return {
            "evaluation_label": "SYNTHETIC GRAPH GROUND TRUTH",
            "ground_truth_status": "SYNTHETIC_GROUND_TRUTH_AVAILABLE",
            "node_count_error": node_error,
            "edge_count_error": edge_error,
            "total_length_error_m": round(length_error, 4),
            "defect_association_accuracy_percent": assoc_accuracy,
            "reconstructed_node_count": calc_node_count,
            "reconstructed_edge_count": calc_edge_count,
            "reconstructed_total_length_m": round(calc_total_len, 3),
            "network_condition_score": (
                graph.analytics.overall_network_condition_score
                if graph.analytics
                else None
            ),
        }

    @staticmethod
    def evaluate_real_data_compatibility() -> dict[str, Any]:
        """Real-data compatibility evaluator. Reports GRAPH_GROUND_TRUTH_UNAVAILABLE if GIS ground truth is missing."""
        return {
            "evaluation_label": "REAL_DATA_GRAPH_COMPATIBILITY",
            "ground_truth_status": "GRAPH_GROUND_TRUTH_UNAVAILABLE",
            "notes": (
                "Real-world inspection data lacks external GIS network/manhole ground truth; "
                "single-pipe linear topology is reconstructed from longitudinal inspection distance."
            ),
        }
