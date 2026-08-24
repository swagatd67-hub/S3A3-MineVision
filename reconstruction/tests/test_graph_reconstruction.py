"""Comprehensive Test Suite for Phase 26 Graph Reconstruction and Network Analytics."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any

# Pre-import backend orchestrator to prevent circular package init cycles
import backend.app.services.mission.orchestrator  # noqa: F401
from digital_twin.models import DigitalTwinState, SynchronizationStatus
from mapping.models import MapObservation, PipeInspectionMap
from reconstruction.defect_models import (
    Projected3DDefect,
    ProjectionStatus,
    Source2DGeometry,
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
    DefectOwnershipStatus,
    FlowDirection,
    GraphEdge,
    GraphNode,
    GraphQualityState,
    NodeType,
)
from reconstruction.models import Point3D, ScaleStatus
from reconstruction.synthetic_graph_scene import SyntheticGraphSceneGenerator


def test_node_and_edge_construction() -> None:
    builder = PipeNetworkGraphBuilder(segment_length_m=1.0)
    graph = builder.build_graph(mission_id="m_test_1", network_id="net_test_1")

    assert graph.graph_id == "graph_net_test_1"
    assert graph.network_id == "net_test_1"
    assert graph.quality_state == GraphQualityState.DEGRADED  # Scale status UNAVAILABLE
    assert len(graph.nodes) > 0
    assert len(graph.edges) > 0

    # Start node and end node checks
    start_node = graph.nodes[0]
    assert start_node.node_type == NodeType.PIPE_ENDPOINT
    assert start_node.longitudinal_s_m == 0.0

    end_node = graph.nodes[-1]
    assert end_node.node_type == NodeType.PIPE_ENDPOINT


def test_deterministic_identities_and_duplicate_prevention() -> None:
    builder = PipeNetworkGraphBuilder(segment_length_m=1.0)
    g1 = builder.build_graph(mission_id="m_det", network_id="net_det")
    g2 = builder.build_graph(mission_id="m_det", network_id="net_det")

    assert g1.graph_id == g2.graph_id
    assert [n.node_id for n in g1.nodes] == [n.node_id for n in g2.nodes]
    assert [e.edge_id for e in g1.edges] == [e.edge_id for e in g2.edges]

    # Ingesting the same topology produces no duplicate node or edge IDs
    node_ids = [n.node_id for n in g1.nodes]
    edge_ids = [e.edge_id for e in g1.edges]
    assert len(node_ids) == len(set(node_ids))
    assert len(edge_ids) == len(set(edge_ids))


def test_topological_connectivity_metrics() -> None:
    nodes = [
        GraphNode("n1", NodeType.PIPE_ENDPOINT, Point3D(0, 0, 0), 0.0, "N1", "test"),
        GraphNode("n2", NodeType.JUNCTION, Point3D(5, 0, 0), 5.0, "N2", "test"),
        GraphNode("n3", NodeType.PIPE_ENDPOINT, Point3D(10, 0, 0), 10.0, "N3", "test"),
        GraphNode("n4_iso", NodeType.MANHOLE, Point3D(0, 5, 0), 0.0, "N4", "test"),
    ]
    edges = [
        GraphEdge("e1", "n1", "n2", 5.0, 300.0, FlowDirection.UNKNOWN, None, ScaleStatus.ESTABLISHED, GraphQualityState.VALID),
        GraphEdge("e2", "n2", "n3", 5.0, 300.0, FlowDirection.UNKNOWN, None, ScaleStatus.ESTABLISHED, GraphQualityState.VALID),
    ]

    conn = compute_network_connectivity(nodes, edges)

    assert conn.total_nodes == 4
    assert conn.total_edges == 2
    assert conn.node_degrees["n1"] == 1
    assert conn.node_degrees["n2"] == 2
    assert conn.node_degrees["n3"] == 1
    assert conn.node_degrees["n4_iso"] == 0

    assert conn.connected_components_count == 2
    assert "n4_iso" in conn.isolated_node_ids
    assert conn.parallel_edge_count == 0
    assert conn.self_loop_count == 0


def test_defect_to_edge_association_and_ambiguity() -> None:
    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    d_interior = Projected3DDefect(
        projection_id="p_int",
        observation_id="obs_int",
        mission_id="m_assoc",
        class_code="CR",
        ai_confidence=0.9,
        projection_confidence=0.95,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=0.5, y=0.0, z=0.15),
        longitudinal_distance_m=0.5,
        angular_position_rad=0.0,
        radial_position_m=0.15,
        scale_status=ScaleStatus.ESTABLISHED,
        quality_state=ProjectionStatus.VALID,
    )
    d_boundary = Projected3DDefect(
        projection_id="p_bound",
        observation_id="obs_bound",
        mission_id="m_assoc",
        class_code="BS",
        ai_confidence=0.9,
        projection_confidence=0.95,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=1.0, y=0.0, z=0.15),
        longitudinal_distance_m=1.0,
        angular_position_rad=0.0,
        radial_position_m=0.15,
        scale_status=ScaleStatus.ESTABLISHED,
        quality_state=ProjectionStatus.VALID,
    )

    pipe_map = PipeInspectionMap(
        mission_id="m_assoc",
        total_inspected_distance_m=2.0,
        start_distance_m=0.0,
        end_distance_m=2.0,
        observation_count=2,
        observations=(),
    )

    builder = PipeNetworkGraphBuilder(segment_length_m=1.0)
    graph = builder.build_graph(
        mission_id="m_assoc",
        network_id="net_assoc",
        pipe_map=pipe_map,
        defects=(d_interior, d_boundary),
    )

    assert len(graph.edges) == 2

    # Edge 0 [0.0, 1.0) should own d_interior uniquely and d_boundary ambiguously
    e0 = graph.edges[0]
    assert e0.defect_count == 2
    assert e0.defects[0].projection_id == "p_int"
    assert e0.defects[0].ownership_status == DefectOwnershipStatus.UNIQUE_OWNER
    assert e0.defects[1].projection_id == "p_bound"
    assert e0.defects[1].ownership_status == DefectOwnershipStatus.AMBIGUOUS

    # Edge 1 [1.0, 2.0] should own d_boundary ambiguously
    e1 = graph.edges[1]
    assert e1.defect_count == 1
    assert e1.defects[0].projection_id == "p_bound"
    assert e1.defects[0].ownership_status == DefectOwnershipStatus.AMBIGUOUS


def test_heuristic_priority_ranking() -> None:
    p_pristine = calculate_edge_priority_score(condition_score=100.0, defect_density_per_m=0.0)
    assert p_pristine == 0.0

    p_degraded = calculate_edge_priority_score(
        condition_score=50.0,
        defect_density_per_m=2.0,
        max_deformation_percent=5.0,
    )
    # (100-50)*0.6 = 30; density = 20; deformation = 7.5 -> 57.5
    assert math.isclose(p_degraded, 57.5, abs_tol=1e-2)


def test_network_analytics_and_coverage() -> None:
    nodes = [
        GraphNode("n1", NodeType.PIPE_ENDPOINT, Point3D(0, 0, 0), 0.0, "N1", "test"),
        GraphNode("n2", NodeType.PIPE_ENDPOINT, Point3D(10, 0, 0), 10.0, "N2", "test"),
    ]
    edges = [
        GraphEdge(
            edge_id="e1",
            source_node_id="n1",
            target_node_id="n2",
            length_m=10.0,
            diameter_mm=300.0,
            flow_direction=FlowDirection.UPSTREAM_TO_DOWNSTREAM,
            reconstruction_id="rec1",
            scale_status=ScaleStatus.ESTABLISHED,
            quality_state=GraphQualityState.VALID,
            defect_count=5,
            defect_density_per_m=0.5,
            condition_score=70.0,
            priority_score=45.0,
        )
    ]

    analytics = generate_network_analytics("net_analytics_test", nodes, edges)
    assert analytics.total_network_length_m == 10.0
    assert analytics.inspected_network_length_m == 10.0
    assert analytics.inspected_coverage_percent == 100.0
    assert analytics.overall_network_condition_score == 70.0
    assert "e1" in analytics.high_priority_edge_ids


def test_graph_quality_and_serialization() -> None:
    builder = PipeNetworkGraphBuilder(segment_length_m=1.0)
    graph = builder.build_graph(mission_id="m_ser", network_id="net_ser")

    graph_dict = graph.to_dict()
    assert graph_dict["graph_id"] == "graph_net_ser"
    assert graph_dict["network_id"] == "net_ser"
    assert graph_dict["graph_version"] == "Phase26_v1"
    assert "nodes" in graph_dict
    assert "edges" in graph_dict
    assert "analytics" in graph_dict
    assert "limitations" in graph_dict


def test_digital_twin_and_mapping_bridges() -> None:
    builder = PipeNetworkGraphBuilder(segment_length_m=1.0)
    graph = builder.build_graph(mission_id="m_bridge", network_id="net_bridge")

    # 1. Digital Twin Bridge
    twin_state = DigitalTwinState(
        robot_id="r1",
        mission_id="m_bridge",
        last_updated_at=datetime.now(timezone.utc),
        synchronization_status=SynchronizationStatus.SYNCHRONIZED.value,
        robot_state=None,
        mission_state=None,
    )
    twin_dict = associate_graph_with_digital_twin(twin_state, graph)
    assert "pipe_network_graph" in twin_dict
    assert twin_dict["pipe_network_graph"]["graph_id"] == "graph_net_bridge"

    # 2. Mapping Bridge
    map_obs = MapObservation(
        observation_id="obs_1",
        mission_id="m_bridge",
        frame_index=0,
        timestamp=datetime.now(timezone.utc),
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        distance_m=0.5,
        x=0.5,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        class_code="CR",
        confidence=0.95,
        threshold=0.5,
        box=None,
        localization_quality="TRACKING",
        model_name="sewer_ml",
        model_version="v1",
        source_type="photo",
    )
    pipe_map = PipeInspectionMap(
        mission_id="m_bridge",
        total_inspected_distance_m=1.0,
        start_distance_m=0.0,
        end_distance_m=1.0,
        observation_count=1,
        observations=(map_obs,),
    )
    map_dict = associate_graph_with_mapping(pipe_map, graph)
    assert "pipe_network_graph" in map_dict
    assert map_dict["pipe_network_graph"]["graph_id"] == "graph_net_bridge"


def test_synthetic_graph_ground_truth_accuracy() -> None:
    syn_gen = SyntheticGraphSceneGenerator()
    accuracy_eval = syn_gen.evaluate_graph_accuracy()

    assert accuracy_eval["evaluation_label"] == "SYNTHETIC GRAPH GROUND TRUTH"
    assert accuracy_eval["ground_truth_status"] == "SYNTHETIC_GROUND_TRUTH_AVAILABLE"
    assert accuracy_eval["node_count_error"] == 0
    assert accuracy_eval["edge_count_error"] == 0
    assert accuracy_eval["total_length_error_m"] == 0.0
    assert accuracy_eval["defect_association_accuracy_percent"] == 100.0

    real_eval = SyntheticGraphSceneGenerator.evaluate_real_data_compatibility()
    assert real_eval["ground_truth_status"] == "GRAPH_GROUND_TRUTH_UNAVAILABLE"


def test_failure_handling_and_edge_cases() -> None:
    # 1. Empty Graph Input
    builder = PipeNetworkGraphBuilder()
    empty_graph = builder.build_graph(
        mission_id="m_empty",
        network_id="net_empty",
        defects=(),
        known_nodes=(),
        known_edges=(),
    )
    assert len(empty_graph.nodes) == 0
    assert len(empty_graph.edges) == 0

    # 2. Single Node Graph Input
    single_node = GraphNode("n_single", NodeType.MANHOLE, Point3D(0, 0, 0), 0.0, "Single", "test")
    single_graph = builder.build_graph(
        mission_id="m_single",
        network_id="net_single",
        known_nodes=[single_node],
        known_edges=[],
    )
    assert len(single_graph.nodes) == 1
    assert len(single_graph.edges) == 0
    assert single_graph.analytics is not None
    assert single_graph.analytics.connectivity_metrics.total_nodes == 1


def test_performance_bounded_workload_benchmark() -> None:
    """Benchmark graph reconstruction and network analytics on synthetic workload (100 nodes, 500 edges, 1000 defects).

    LABEL: SYNTHETIC_WORKLOAD_BENCHMARK (Environment Dependent).
    This benchmark measures Python graph algorithmic efficiency in synthetic memory workloads.
    """
    nodes = [
        GraphNode(
            node_id=f"n_bench_{i}",
            node_type=NodeType.JUNCTION if i % 5 == 0 else NodeType.PIPE_ENDPOINT,
            position_3d=Point3D(x=(i % 10) * 2.0, y=(i // 10) * 2.0, z=0.0),
            longitudinal_s_m=(i % 10) * 2.0,
            label=f"Node {i}",
            provenance_source="BenchmarkWorkload",
        )
        for i in range(100)
    ]

    edges_data: list[dict[str, Any]] = []
    for i in range(500):
        src = f"n_bench_{i % 100}"
        tgt = f"n_bench_{(i + 1) % 100}"
        edges_data.append(
            {
                "edge_id": f"e_bench_{i}",
                "source_node_id": src,
                "target_node_id": tgt,
                "length_m": 2.0,
                "diameter_mm": 300.0,
                "flow_direction": FlowDirection.UNKNOWN.value,
                "condition_score": 80.0 - (i % 30),
            }
        )

    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    defects: list[Projected3DDefect] = []
    for i in range(1000):
        defects.append(
            Projected3DDefect(
                projection_id=f"p_bench_{i}",
                observation_id=f"obs_bench_{i}",
                mission_id="m_bench",
                class_code="CR" if i % 2 == 0 else "DE",
                ai_confidence=0.9,
                projection_confidence=0.95,
                source_2d_geometry=src_geom,
                point_3d=Point3D(x=(i % 10) * 2.0, y=0.0, z=0.15),
                longitudinal_distance_m=(i % 10) * 2.0,
                angular_position_rad=0.0,
                radial_position_m=0.15,
                scale_status=ScaleStatus.ESTABLISHED,
                quality_state=ProjectionStatus.VALID,
            )
        )

    builder = PipeNetworkGraphBuilder()
    t0 = time.perf_counter()
    graph = builder.build_graph(
        mission_id="m_bench",
        network_id="net_bench",
        defects=defects,
        known_nodes=nodes,
        known_edges=edges_data,
    )
    elapsed_sec = time.perf_counter() - t0

    assert len(graph.nodes) == 100
    assert len(graph.edges) == 500
    assert graph.analytics is not None
    assert graph.analytics.total_defects == 1000
    assert elapsed_sec < 1.5
