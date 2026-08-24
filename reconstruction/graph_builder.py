"""Deterministic Pipe Network Graph Builder and Defect-to-Edge Associator (Phase 26)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from mapping.models import PipeInspectionMap
from reconstruction.analysis_models import Pipe3DAnalysisReport
from reconstruction.defect_models import Projected3DDefect
from reconstruction.graph_analytics import (
    calculate_edge_priority_score,
    generate_network_analytics,
)
from reconstruction.graph_models import (
    DefectOnEdge,
    DefectOwnershipStatus,
    FlowDirection,
    GraphEdge,
    GraphNode,
    GraphQualityState,
    NodeType,
    PipeNetworkGraph,
)
from reconstruction.models import Point3D, Reconstruction3DOutput, ScaleStatus


class PipeNetworkGraphBuilder:
    """Core builder engine for constructing deterministic 3D pipe network topology and performing spatial graph associations."""

    def __init__(self, segment_length_m: float = 1.0) -> None:
        self.segment_length_m = max(0.25, segment_length_m)

    def build_graph(
        self,
        mission_id: str = "unknown_mission",
        network_id: str | None = None,
        pipe_map: PipeInspectionMap | None = None,
        reconstruction: Reconstruction3DOutput | None = None,
        analysis_report: Pipe3DAnalysisReport | None = None,
        defects: Sequence[Projected3DDefect] | None = None,
        known_nodes: Sequence[GraphNode | dict[str, Any]] | None = None,
        known_edges: Sequence[dict[str, Any]] | None = None,
        flow_direction: FlowDirection = FlowDirection.UNKNOWN,
    ) -> PipeNetworkGraph:
        """Construct a deterministic pipe network graph from mapping, 3D reconstruction, and Phase 25 analysis outputs."""
        net_id = network_id or f"net_{mission_id}"
        graph_id = f"graph_{net_id}"

        # 1. Determine scale status & quality state
        scale_status = ScaleStatus.UNAVAILABLE
        if reconstruction:
            scale_status = reconstruction.scale_status
        elif analysis_report:
            scale_status = analysis_report.scale_status

        quality_state = GraphQualityState.VALID
        if scale_status == ScaleStatus.UNAVAILABLE:
            quality_state = GraphQualityState.DEGRADED

        limitations: list[str] = [
            (
                "Priority score is classified as DERIVED_HEURISTIC_PRIORITY (Heuristic_Priority_v1) "
                "and does not constitute a certified civil infrastructure maintenance decision standard."
            )
        ]
        if flow_direction == FlowDirection.UNKNOWN:
            limitations.append("Flow direction is UNKNOWN; upstream/downstream orientation is not inferred from arbitrary coordinates.")
        if scale_status == ScaleStatus.UNAVAILABLE:
            limitations.append("Scale status is UNAVAILABLE; spatial edge lengths are uncalibrated.")

        # 2. Extract defects list
        all_defects: list[Projected3DDefect] = []
        if defects:
            all_defects.extend(defects)

        baseline_diameter_mm = 300.0
        if reconstruction and reconstruction.baseline_diameter_mm is not None:
            baseline_diameter_mm = reconstruction.baseline_diameter_mm

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # 3. Construct Nodes and Edges
        if known_nodes is not None and known_edges is not None:
            # Custom / Synthetic / GIS Graph Input
            nodes = self._parse_known_nodes(known_nodes)
            edges = self._parse_known_edges(known_edges, baseline_diameter_mm, scale_status, flow_direction)
        else:
            # Linear Inspection Topology Reconstruction
            total_length_m = 0.0
            if reconstruction and reconstruction.centerline:
                total_length_m = reconstruction.centerline.total_length_m
            elif pipe_map and pipe_map.end_distance_m is not None:
                total_length_m = pipe_map.end_distance_m
            elif all_defects:
                valid_s = [d.longitudinal_distance_m for d in all_defects if d.longitudinal_distance_m is not None]
                total_length_m = max(valid_s) if valid_s else 0.0

            analyzed_len = max(0.1, total_length_m)
            num_segments = max(1, math.ceil(analyzed_len / self.segment_length_m))

            # Build deterministic node sequence along pipe s
            node_map: dict[int, GraphNode] = {}
            for i in range(num_segments + 1):
                s_pos = min(analyzed_len, i * self.segment_length_m)
                is_start = (i == 0)
                is_end = (i == num_segments)

                node_id = f"node_{mission_id}_s{round(s_pos, 3):.3f}".replace(".", "_")
                node_type = (
                    NodeType.PIPE_ENDPOINT
                    if (is_start or is_end)
                    else NodeType.INSPECTION_REFERENCE
                )
                node_label = f"Endpoint s={round(s_pos, 2)}m" if (is_start or is_end) else f"Ref s={round(s_pos, 2)}m"

                gn = GraphNode(
                    node_id=node_id,
                    node_type=node_type,
                    position_3d=Point3D(x=s_pos, y=0.0, z=0.0),
                    longitudinal_s_m=s_pos,
                    label=node_label,
                    provenance_source=f"InspectionMap_{mission_id}",
                    metadata={"mission_id": mission_id},
                )
                node_map[i] = gn
                nodes.append(gn)

            # Build deterministic edge sequence connecting nodes
            for seg_idx in range(num_segments):
                src_node = node_map[seg_idx]
                tgt_node = node_map[seg_idx + 1]
                assert src_node.longitudinal_s_m is not None
                assert tgt_node.longitudinal_s_m is not None

                edge_len = max(0.1, tgt_node.longitudinal_s_m - src_node.longitudinal_s_m)
                edge_id = f"edge_{src_node.node_id}_to_{tgt_node.node_id}"

                # Match Phase 25 condition section if available
                sec_cond_score: float | None = None
                sec_def_pct: float | None = None
                if analysis_report and seg_idx < len(analysis_report.sections):
                    sec = analysis_report.sections[seg_idx]
                    sec_cond_score = sec.condition_score
                    if sec.deformation_metrics:
                        sec_def_pct = sec.deformation_metrics.max_deformation_percent

                edge_rec_id = reconstruction.reconstruction_id if reconstruction else None

                edges.append(
                    GraphEdge(
                        edge_id=edge_id,
                        source_node_id=src_node.node_id,
                        target_node_id=tgt_node.node_id,
                        length_m=edge_len,
                        diameter_mm=baseline_diameter_mm,
                        flow_direction=flow_direction,
                        reconstruction_id=edge_rec_id,
                        scale_status=scale_status,
                        quality_state=quality_state,
                        condition_score=sec_cond_score,
                        max_deformation_percent=sec_def_pct,
                        metadata={
                            "start_s_m": src_node.longitudinal_s_m,
                            "end_s_m": tgt_node.longitudinal_s_m,
                        },
                    )
                )

        # 4. Perform Defect-to-Edge Association
        enriched_edges = self._associate_defects_to_edges(edges, nodes, all_defects)

        # 5. Generate Network Analytics
        analytics = generate_network_analytics(net_id, nodes, enriched_edges)

        return PipeNetworkGraph(
            graph_id=graph_id,
            network_id=net_id,
            mission_id=mission_id,
            nodes=tuple(nodes),
            edges=tuple(enriched_edges),
            scale_status=scale_status,
            quality_state=quality_state,
            analytics=analytics,
            graph_version="Phase26_v1",
            coordinate_frame="LOCAL_INSPECTION_FRAME",
            limitations=tuple(limitations),
        )

    def _associate_defects_to_edges(
        self,
        edges: list[GraphEdge],
        nodes: list[GraphNode],
        defects: list[Projected3DDefect],
    ) -> list[GraphEdge]:
        """Associate projected 3D defects with specific graph edges based on longitudinal coordinates."""
        node_lookup = {n.node_id: n for n in nodes}
        edge_defects_map: dict[str, list[DefectOnEdge]] = {e.edge_id: [] for e in edges}

        num_edges = len(edges)
        for d in defects:
            if d.longitudinal_distance_m is None:
                continue

            s = d.longitudinal_distance_m

            for idx, edge in enumerate(edges):
                src_n = node_lookup.get(edge.source_node_id)
                tgt_n = node_lookup.get(edge.target_node_id)

                if src_n is None or tgt_n is None:
                    continue
                if src_n.longitudinal_s_m is None or tgt_n.longitudinal_s_m is None:
                    continue

                s_start = min(src_n.longitudinal_s_m, tgt_n.longitudinal_s_m)
                s_end = max(src_n.longitudinal_s_m, tgt_n.longitudinal_s_m)
                is_last_edge = (idx == num_edges - 1)

                is_boundary = (abs(s - s_start) < 1e-5 or abs(s - s_end) < 1e-5)
                # Boundary determinism: [s_start, s_end) for interior edges, [s_start, s_end] for final edge
                in_edge = (
                    (s_start <= s <= s_end + 1e-6)
                    if (is_last_edge or is_boundary)
                    else (s_start <= s < s_end)
                )

                if in_edge:
                    ownership = (
                        DefectOwnershipStatus.AMBIGUOUS
                        if is_boundary
                        else DefectOwnershipStatus.UNIQUE_OWNER
                    )

                    dfe = DefectOnEdge(
                        projection_id=d.projection_id,
                        observation_id=d.observation_id,
                        class_code=d.class_code,
                        longitudinal_s_m=s,
                        angular_theta_rad=d.angular_position_rad,
                        ownership_status=ownership,
                        confidence=d.projection_confidence,
                    )
                    edge_defects_map[edge.edge_id].append(dfe)

        # Enrich edges with defect counts, densities, and heuristic priority scores
        result_edges: list[GraphEdge] = []
        for edge in edges:
            edge_defs = tuple(edge_defects_map.get(edge.edge_id, []))
            def_count = len(edge_defs)
            density = def_count / max(0.1, edge.length_m)

            p_score = calculate_edge_priority_score(
                condition_score=edge.condition_score,
                defect_density_per_m=density,
                max_deformation_percent=edge.max_deformation_percent,
            )

            result_edges.append(
                GraphEdge(
                    edge_id=edge.edge_id,
                    source_node_id=edge.source_node_id,
                    target_node_id=edge.target_node_id,
                    length_m=edge.length_m,
                    diameter_mm=edge.diameter_mm,
                    flow_direction=edge.flow_direction,
                    reconstruction_id=edge.reconstruction_id,
                    scale_status=edge.scale_status,
                    quality_state=edge.quality_state,
                    defects=edge_defs,
                    defect_count=def_count,
                    defect_density_per_m=density,
                    max_deformation_percent=edge.max_deformation_percent,
                    condition_score=edge.condition_score,
                    score_classification=edge.score_classification,
                    priority_score=p_score,
                    priority_classification="DERIVED_HEURISTIC_PRIORITY",
                    quality_notes=edge.quality_notes,
                    metadata=edge.metadata,
                )
            )

        return result_edges

    def _parse_known_nodes(
        self, known_nodes: Sequence[GraphNode | dict[str, Any]]
    ) -> list[GraphNode]:
        """Parse raw dictionary or object node definitions into GraphNode models."""
        parsed: list[GraphNode] = []
        for item in known_nodes:
            if isinstance(item, GraphNode):
                parsed.append(item)
            elif isinstance(item, dict):
                pos = None
                if item.get("position_3d"):
                    p = item["position_3d"]
                    pos = Point3D(x=p["x"], y=p["y"], z=p["z"])
                parsed.append(
                    GraphNode(
                        node_id=str(item["node_id"]),
                        node_type=NodeType(item.get("node_type", NodeType.UNKNOWN.value)),
                        position_3d=pos,
                        longitudinal_s_m=item.get("longitudinal_s_m"),
                        label=str(item.get("label", item["node_id"])),
                        provenance_source=str(item.get("provenance_source", "custom_input")),
                        metadata=dict(item.get("metadata", {})),
                    )
                )
        return parsed

    def _parse_known_edges(
        self,
        known_edges: Sequence[dict[str, Any]],
        baseline_diameter_mm: float,
        scale_status: ScaleStatus,
        flow_direction: FlowDirection,
    ) -> list[GraphEdge]:
        """Parse raw dictionary edge definitions into GraphEdge models."""
        parsed: list[GraphEdge] = []
        for item in known_edges:
            edge_id = str(item["edge_id"])
            src_id = str(item["source_node_id"])
            tgt_id = str(item["target_node_id"])
            length_m = max(0.1, float(item.get("length_m", 1.0)))
            diameter_mm = float(item.get("diameter_mm", baseline_diameter_mm))
            flow_dir = FlowDirection(item.get("flow_direction", flow_direction.value))

            parsed.append(
                GraphEdge(
                    edge_id=edge_id,
                    source_node_id=src_id,
                    target_node_id=tgt_id,
                    length_m=length_m,
                    diameter_mm=diameter_mm,
                    flow_direction=flow_dir,
                    reconstruction_id=item.get("reconstruction_id"),
                    scale_status=scale_status,
                    quality_state=GraphQualityState(
                        item.get("quality_state", GraphQualityState.VALID.value)
                    ),
                    condition_score=item.get("condition_score"),
                    max_deformation_percent=item.get("max_deformation_percent"),
                    metadata=dict(item.get("metadata", {})),
                )
            )
        return parsed
