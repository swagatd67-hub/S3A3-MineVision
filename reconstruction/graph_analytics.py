"""Network Analytics, Connectivity Diagnostics, and Heuristic Priority Scoring (Phase 26)."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence

from reconstruction.graph_models import (
    GraphEdge,
    GraphNode,
    NetworkAnalyticsSummary,
    NetworkConnectivityMetrics,
    NodeType,
)


def compute_network_connectivity(
    nodes: Sequence[GraphNode],
    edges: Sequence[GraphEdge],
) -> NetworkConnectivityMetrics:
    """Compute topological connectivity metrics, degree counts, and component structures."""
    node_ids = {n.node_id for n in nodes}
    degrees: dict[str, int] = {nid: 0 for nid in node_ids}

    adjacency: dict[str, set[str]] = defaultdict(set)
    parallel_edge_count = 0
    self_loop_count = 0
    seen_edge_pairs: set[tuple[str, str]] = set()

    for edge in edges:
        u = edge.source_node_id
        v = edge.target_node_id

        if u in degrees:
            degrees[u] += 1
        if v in degrees:
            degrees[v] += 1

        if u == v:
            self_loop_count += 1
        else:
            pair = (min(u, v), max(u, v))
            if pair in seen_edge_pairs:
                parallel_edge_count += 1
            else:
                seen_edge_pairs.add(pair)

            adjacency[u].add(v)
            adjacency[v].add(u)

    # Connected Components search (BFS)
    visited: set[str] = set()
    components: list[tuple[str, ...]] = []

    for nid in sorted(node_ids):
        if nid not in visited:
            comp: list[str] = []
            queue = deque([nid])
            visited.add(nid)

            while queue:
                curr = queue.popleft()
                comp.append(curr)
                for nbr in sorted(adjacency[curr]):
                    if nbr not in visited:
                        visited.add(nbr)
                        queue.append(nbr)

            components.append(tuple(sorted(comp)))

    isolated_node_ids = tuple(
        sorted(nid for nid, deg in degrees.items() if deg == 0)
    )
    dangling_endpoint_ids = tuple(
        sorted(
            n.node_id
            for n in nodes
            if degrees.get(n.node_id, 0) == 1 and n.node_type == NodeType.PIPE_ENDPOINT
        )
    )

    disconnected_segment_count = max(0, len(components) - 1)

    return NetworkConnectivityMetrics(
        total_nodes=len(nodes),
        total_edges=len(edges),
        node_degrees=degrees,
        connected_components_count=len(components),
        component_node_lists=tuple(components),
        isolated_node_ids=isolated_node_ids,
        dangling_endpoint_ids=dangling_endpoint_ids,
        parallel_edge_count=parallel_edge_count,
        self_loop_count=self_loop_count,
        disconnected_segment_count=disconnected_segment_count,
    )


def calculate_edge_priority_score(
    condition_score: float | None,
    defect_density_per_m: float,
    max_deformation_percent: float | None = None,
) -> float:
    """Calculate DERIVED HEURISTIC priority score (0.0 to 100.0) for inspection/maintenance ranking.

    FORMULA VERSION: Heuristic_Priority_v1
    CLASSIFICATION: DERIVED_HEURISTIC_PRIORITY
    LIMITATION: This priority index is a preliminary candidate ranking formula and must NOT be
    presented or used as a certified civil engineering asset maintenance decision standard.

    Formula:
        PriorityScore = min(100.0, (100.0 - ConditionScore) * 0.6 + (DefectDensity * 10.0) + (MaxDeformation * 1.5))
    """
    cond_val = condition_score if condition_score is not None else 100.0
    cond_penalty = (100.0 - cond_val) * 0.6

    density_bonus = defect_density_per_m * 10.0

    def_bonus = 0.0
    if max_deformation_percent is not None and max_deformation_percent > 0.0:
        def_bonus = min(30.0, max_deformation_percent * 1.5)

    raw_priority = cond_penalty + density_bonus + def_bonus
    return round(min(100.0, max(0.0, raw_priority)), 2)


def generate_network_analytics(
    network_id: str,
    nodes: Sequence[GraphNode],
    edges: Sequence[GraphEdge],
) -> NetworkAnalyticsSummary:
    """Compute overall network analytics, high-defect edge identification, and heuristic priority ranking."""
    connectivity = compute_network_connectivity(nodes, edges)

    total_len = sum(e.length_m for e in edges)
    inspected_len = sum(
        e.length_m for e in edges if e.quality_state.value != "INSUFFICIENT_DATA"
    )
    coverage_pct = (
        round((inspected_len / max(0.1, total_len)) * 100.0, 2) if total_len > 0 else 0.0
    )

    unique_defect_ids = {
        d.projection_id for e in edges for d in e.defects
    }
    total_defects = len(unique_defect_ids)
    mean_density = total_defects / max(0.1, total_len) if total_len > 0 else 0.0

    valid_scores = [e.condition_score for e in edges if e.condition_score is not None]
    overall_score = (
        sum(valid_scores) / len(valid_scores) if valid_scores else 100.0
    )

    # High defect edge identification (density >= 1.0 or defect_count >= 3)
    high_defect_edges = tuple(
        e.edge_id
        for e in sorted(edges, key=lambda x: x.defect_density_per_m, reverse=True)
        if e.defect_density_per_m >= 1.0 or e.defect_count >= 3
    )

    # High priority edge ranking (priority_score >= 40.0)
    high_priority_edges = tuple(
        e.edge_id
        for e in sorted(edges, key=lambda x: (x.priority_score or 0.0), reverse=True)
        if (e.priority_score is not None and e.priority_score >= 40.0)
    )

    return NetworkAnalyticsSummary(
        network_id=network_id,
        total_network_length_m=total_len,
        inspected_network_length_m=inspected_len,
        inspected_coverage_percent=coverage_pct,
        total_defects=total_defects,
        mean_defect_density_per_m=mean_density,
        overall_network_condition_score=overall_score,
        high_defect_edge_ids=high_defect_edges,
        high_priority_edge_ids=high_priority_edges,
        connectivity_metrics=connectivity,
        analytics_version="Phase26_v1",
        priority_scoring_version="Heuristic_Priority_v1",
        priority_classification="DERIVED_HEURISTIC_PRIORITY",
    )
