"""Additive Integration Bridges for Digital Twin and Mapping Domains (Phase 26)."""

from __future__ import annotations

from typing import Any

from digital_twin.models import DigitalTwinState
from mapping.models import PipeInspectionMap
from reconstruction.graph_models import PipeNetworkGraph


def associate_graph_with_digital_twin(
    twin_state: DigitalTwinState,
    graph: PipeNetworkGraph,
) -> dict[str, Any]:
    """Additive integration bridge: Attach reconstructed Pipe Network Graph to DigitalTwinState without mutating core schema."""
    base_dict = twin_state.to_dict()
    base_dict["pipe_network_graph"] = graph.to_dict()
    return base_dict


def associate_graph_with_mapping(
    pipe_map: PipeInspectionMap,
    graph: PipeNetworkGraph,
) -> dict[str, Any]:
    """Additive integration bridge: Attach reconstructed Pipe Network Graph to PipeInspectionMap without mutating core schema."""
    base_dict = pipe_map.to_dict()
    base_dict["pipe_network_graph"] = graph.to_dict()
    return base_dict
