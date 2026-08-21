"""Analytical Engine for Sewer Pipe Cleaning Effectiveness Comparison."""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.services.inspection.models import FusedInspectionObservation
from cleaning.models import CleaningEffectiveness, CleaningOperation
from mapping.models import MapObservation, PipeInspectionMap


def _extract_observations(
    data: Sequence[FusedInspectionObservation] | Sequence[MapObservation] | PipeInspectionMap,
) -> tuple[str, tuple[FusedInspectionObservation | MapObservation, ...]]:
    """Extract mission_id and sequence of observations from supported data containers."""
    if isinstance(data, PipeInspectionMap):
        return data.mission_id, data.observations

    obs_tuple = tuple(data)
    mission_id = obs_tuple[0].mission_id if len(obs_tuple) > 0 else "unknown"
    return mission_id, obs_tuple


def evaluate_cleaning_effectiveness(
    operation: CleaningOperation,
    before_data: Sequence[FusedInspectionObservation] | Sequence[MapObservation] | PipeInspectionMap,
    after_data: Sequence[FusedInspectionObservation] | Sequence[MapObservation] | PipeInspectionMap,
    require_same_mission: bool = True,
    distance_tolerance_m: float = 0.5,
) -> CleaningEffectiveness:
    """Evaluate pipe cleaning effectiveness by comparing before and after inspection observations.

    Rules & Conditions:
        1. Compares observations within the overlapping longitudinal distance range of the cleaning operation.
        2. Filters out observations with INVALID localization quality.
        3. Flags comparison as UNAVAILABLE if localization quality is incompatible or no overlapping data exists.
        4. Calculates resolved, persistent, and new defect classes deterministically.
        5. Does NOT falsely claim effectiveness if inspection coverage differs or new defects appear.
    """
    before_mission, before_raw = _extract_observations(before_data)
    after_mission, after_raw = _extract_observations(after_data)

    reasons: list[str] = []

    # Validate mission consistency if required
    if require_same_mission:
        if before_mission != operation.mission_id:
            reasons.append(
                f"Before inspection mission '{before_mission}' does not match cleaning operation mission '{operation.mission_id}'."
            )
        if after_mission != operation.mission_id:
            reasons.append(
                f"After inspection mission '{after_mission}' does not match cleaning operation mission '{operation.mission_id}'."
            )

    # Determine spatial distance bounds
    start_dist = operation.start_distance_m
    end_dist = operation.end_distance_m

    if start_dist is None or end_dist is None:
        # Infer bounds from available before observations
        valid_before_dists = [o.distance_m for o in before_raw if o.distance_m is not None]
        if len(valid_before_dists) > 0:
            start_dist = min(valid_before_dists) if start_dist is None else start_dist
            end_dist = max(valid_before_dists) if end_dist is None else end_dist
        else:
            start_dist = 0.0
            end_dist = 0.0

    low_bound = min(float(start_dist), float(end_dist)) - distance_tolerance_m
    high_bound = max(float(start_dist), float(end_dist)) + distance_tolerance_m

    # Filter observations to spatial range and check localization quality
    def _filter_obs(
        raw_list: tuple[FusedInspectionObservation | MapObservation, ...],
    ) -> tuple[list[FusedInspectionObservation | MapObservation], bool]:
        filtered = []
        has_invalid_localization = False
        for obs in raw_list:
            d = obs.distance_m
            if d is not None and low_bound <= float(d) <= high_bound:
                if obs.localization_quality == "INVALID":
                    has_invalid_localization = True
                else:
                    filtered.append(obs)
        return filtered, has_invalid_localization

    before_filtered, before_invalid_loc = _filter_obs(before_raw)
    after_filtered, after_invalid_loc = _filter_obs(after_raw)

    if before_invalid_loc or after_invalid_loc:
        reasons.append("Incompatible localization quality: one or more observations had INVALID localization.")

    if len(before_filtered) == 0 and len(after_filtered) == 0:
        reasons.append("No valid observations found within the cleaning distance region.")

    # Check model provenance compatibility
    before_models = {o.model_name for o in before_filtered}
    after_models = {o.model_name for o in after_filtered}
    if len(before_models) > 0 and len(after_models) > 0 and before_models != after_models:
        reasons.append(f"Incompatible perception model provenance: before={before_models}, after={after_models}.")

    # If any blocking reason exists, return UNAVAILABLE result
    if len(reasons) > 0:
        before_classes = sorted({o.class_code for o in before_filtered})
        after_classes = sorted({o.class_code for o in after_filtered})

        return CleaningEffectiveness(
            operation_id=operation.operation_id,
            mission_id=operation.mission_id,
            start_distance_m=float(start_dist),
            end_distance_m=float(end_dist),
            before_observation_count=len(before_filtered),
            after_observation_count=len(after_filtered),
            before_defect_classes=tuple(before_classes),
            after_defect_classes=tuple(after_classes),
            resolved_defect_classes=(),
            persistent_defect_classes=(),
            new_defect_classes=(),
            defect_count_change=len(after_filtered) - len(before_filtered),
            measurable_change=False,
            confidence="UNAVAILABLE",
            is_effective=None,
            unavailable_reasons=tuple(reasons),
        )

    # Perform before/after comparison
    before_set = {o.class_code for o in before_filtered}
    after_set = {o.class_code for o in after_filtered}

    resolved = sorted(before_set - after_set)
    persistent = sorted(before_set & after_set)
    new_defects = sorted(after_set - before_set)

    count_change = len(after_filtered) - len(before_filtered)
    measurable_change = True

    # Effectiveness criteria: count decreased AND no new defect classes appeared
    is_effective: bool = (len(after_filtered) < len(before_filtered)) and (len(new_defects) == 0)
    confidence: str = "HIGH" if (len(before_filtered) > 0 and len(after_filtered) > 0) else "MEDIUM"

    return CleaningEffectiveness(
        operation_id=operation.operation_id,
        mission_id=operation.mission_id,
        start_distance_m=float(start_dist),
        end_distance_m=float(end_dist),
        before_observation_count=len(before_filtered),
        after_observation_count=len(after_filtered),
        before_defect_classes=tuple(sorted(before_set)),
        after_defect_classes=tuple(sorted(after_set)),
        resolved_defect_classes=tuple(resolved),
        persistent_defect_classes=tuple(persistent),
        new_defect_classes=tuple(new_defects),
        defect_count_change=count_change,
        measurable_change=measurable_change,
        confidence=confidence,
        is_effective=is_effective,
        unavailable_reasons=(),
    )
