"""Pipe Inspection Map Builder Service."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone

from backend.app.services.inspection.models import FusedInspectionObservation
from mapping.exceptions import MixedMissionError
from mapping.models import MapObservation, MapTrajectoryPoint, PipeInspectionMap


def _sort_key(obs: MapObservation) -> tuple[float, datetime, str]:
    ts = (
        obs.timestamp
        if obs.timestamp is not None
        else datetime.min.replace(tzinfo=timezone.utc)
    )
    return (obs.distance_m, ts, obs.observation_id)


def build_inspection_map(
    observations: Sequence[FusedInspectionObservation],
    mission_id: str | None = None,
    trajectory_points: Sequence[MapTrajectoryPoint] | None = None,
) -> PipeInspectionMap:
    """Build a spatial PipeInspectionMap from a sequence of FusedInspectionObservation objects.

    Parameters:
        observations: Sequence of fused inspection observations.
        mission_id: Target mission ID (optional). If None and multiple mission IDs exist, raises MixedMissionError.
        trajectory_points: Optional trajectory snapshot points along the map.

    Returns:
        PipeInspectionMap: Immutable spatial pipe inspection map.
    """
    if not observations:
        target_mission = mission_id if mission_id is not None else "unknown"
        traj_summary = tuple(trajectory_points) if trajectory_points else ()
        return PipeInspectionMap(
            mission_id=target_mission,
            total_inspected_distance_m=0.0,
            start_distance_m=None,
            end_distance_m=None,
            observation_count=0,
            observations=(),
            trajectory_summary=traj_summary,
        )

    # Mission Validation & Filtering
    distinct_missions = sorted({obs.mission_id for obs in observations if obs.mission_id})

    if mission_id is not None:
        target_mission = mission_id
        filtered_obs = [obs for obs in observations if obs.mission_id == mission_id]
    else:
        if len(distinct_missions) > 1:
            raise MixedMissionError(
                f"Observations contain multiple distinct mission IDs ({distinct_missions}). "
                "Specify target mission_id parameter or filter input observations."
            )
        target_mission = next(iter(distinct_missions), "unknown")
        filtered_obs = list(observations)

    # Deduplication & Conversion
    seen_ids: set[str] = set()
    map_observations: list[MapObservation] = []

    for fused_obs in filtered_obs:
        if fused_obs.observation_id in seen_ids:
            continue
        seen_ids.add(fused_obs.observation_id)
        map_observations.append(MapObservation.from_fused_observation(fused_obs))

    # Sort primarily by distance_m, secondarily by timestamp, tertiarily by observation_id
    map_observations.sort(key=_sort_key)

    # Calculate distance metrics
    valid_distances = [obs.distance_m for obs in map_observations]

    start_dist: float | None = None
    end_dist: float | None = None
    total_dist: float = 0.0

    if valid_distances:
        start_dist = min(valid_distances)
        end_dist = max(valid_distances)
        total_dist = max(0.0, end_dist - start_dist)

    traj_summary = tuple(trajectory_points) if trajectory_points else ()

    return PipeInspectionMap(
        mission_id=target_mission,
        total_inspected_distance_m=total_dist,
        start_distance_m=start_dist,
        end_distance_m=end_dist,
        observation_count=len(map_observations),
        observations=tuple(map_observations),
        trajectory_summary=traj_summary,
    )


def build_inspection_maps_by_mission(
    observations: Sequence[FusedInspectionObservation],
) -> dict[str, PipeInspectionMap]:
    """Group observations by mission_id and build a PipeInspectionMap for each mission."""
    grouped: dict[str, list[FusedInspectionObservation]] = defaultdict(list)
    for obs in observations:
        grouped[obs.mission_id].append(obs)

    return {
        m_id: build_inspection_map(obs_list, mission_id=m_id)
        for m_id, obs_list in grouped.items()
    }
