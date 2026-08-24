"""Pipe Shape, Radius, and Deformation Analysis Engine (Phase 25)."""

from __future__ import annotations

from morphology.models import MorphologySummaryReport
from reconstruction.analysis_models import (
    Deformation3DMetrics,
    MetricAvailabilityStatus,
)
from reconstruction.models import Reconstruction3DOutput, ScaleStatus


def analyze_pipe_deformation(
    reconstruction: Reconstruction3DOutput | None,
    morphology_summary: MorphologySummaryReport | None = None,
) -> Deformation3DMetrics:
    """Analyze local radius, circularity, radial deviation, and deformation percentage across the pipe."""
    # 1. Determine nominal pipe baseline parameters
    nominal_diameter_mm = 300.0
    if reconstruction is not None and reconstruction.baseline_diameter_mm is not None:
        nominal_diameter_mm = reconstruction.baseline_diameter_mm
    elif (
        morphology_summary is not None
        and morphology_summary.mean_observed_diameter_mm is not None
    ):
        nominal_diameter_mm = morphology_summary.mean_observed_diameter_mm

    nominal_radius_m = (nominal_diameter_mm / 1000.0) / 2.0
    notes: list[str] = []

    # 2. Check scale status
    scale_status = ScaleStatus.UNAVAILABLE
    if reconstruction is not None:
        scale_status = reconstruction.scale_status
    elif morphology_summary is not None and morphology_summary.total_observations > 0:
        scale_status = ScaleStatus.ESTIMATED

    if scale_status == ScaleStatus.UNAVAILABLE:
        return Deformation3DMetrics(
            status=MetricAvailabilityStatus.UNAVAILABLE,
            nominal_diameter_mm=nominal_diameter_mm,
            nominal_radius_m=nominal_radius_m,
            mean_measured_radius_m=None,
            min_radius_m=None,
            max_radius_m=None,
            max_radial_deviation_m=None,
            max_deformation_percent=None,
            mean_deformation_percent=None,
            circularity_score=None,
            longitudinal_profile=(),
            notes=("Metric scale is UNAVAILABLE; deformation analysis cannot be performed without valid scale.",),
        )

    metric_status = (
        MetricAvailabilityStatus.ESTABLISHED
        if scale_status == ScaleStatus.ESTABLISHED
        else MetricAvailabilityStatus.ESTIMATED
    )

    # 3. Collect radii measurements from 3D reconstruction surface points or morphology report
    sample_points: list[tuple[float, float]] = []  # (s_m, radius_m)

    if reconstruction is not None and reconstruction.surface_points:
        for pt in reconstruction.surface_points:
            s_m = pt.longitudinal_distance_m
            r_m = (pt.radius_mm / 1000.0) + (pt.radial_offset_mm / 1000.0)
            sample_points.append((s_m, r_m))
    elif morphology_summary is not None and morphology_summary.observations:
        for obs in morphology_summary.observations:
            effective_d_mm = (
                obs.effective_pipe_diameter_mm
                or obs.measured_pipe_diameter_mm
                or obs.estimated_pipe_diameter_mm
            )
            if effective_d_mm is not None:
                r_m = (effective_d_mm / 1000.0) / 2.0
                sample_points.append((obs.distance_m, r_m))

    if not sample_points:
        return Deformation3DMetrics(
            status=MetricAvailabilityStatus.UNAVAILABLE,
            nominal_diameter_mm=nominal_diameter_mm,
            nominal_radius_m=nominal_radius_m,
            mean_measured_radius_m=None,
            min_radius_m=None,
            max_radius_m=None,
            max_radial_deviation_m=None,
            max_deformation_percent=None,
            mean_deformation_percent=None,
            circularity_score=None,
            longitudinal_profile=(),
            notes=("No 3D surface points or morphology observations available for deformation calculation.",),
        )

    # 4. Compute statistical deformation metrics
    radii = [r for _, r in sample_points]
    min_r = min(radii)
    max_r = max(radii)
    mean_r = sum(radii) / len(radii)

    radial_deviations = [abs(r - nominal_radius_m) for r in radii]
    max_radial_dev = max(radial_deviations)

    def_percents = [(abs(r - nominal_radius_m) / nominal_radius_m) * 100.0 for r in radii]
    max_def_pct = max(def_percents)
    mean_def_pct = sum(def_percents) / len(def_percents)

    # Circularity score (1.0 = perfect circle, decreasing with radial spread)
    circularity = max(0.0, 1.0 - ((max_r - min_r) / nominal_radius_m))

    # Build longitudinal profile samples
    profile_dict: dict[float, list[float]] = {}
    for s_m, r_m in sample_points:
        s_bucket = round(s_m, 2)
        if s_bucket not in profile_dict:
            profile_dict[s_bucket] = []
        profile_dict[s_bucket].append(r_m)

    longitudinal_profile: list[dict[str, float]] = []
    for s_bucket in sorted(profile_dict.keys()):
        r_list = profile_dict[s_bucket]
        avg_r = sum(r_list) / len(r_list)
        dev_pct = (abs(avg_r - nominal_radius_m) / nominal_radius_m) * 100.0
        longitudinal_profile.append(
            {
                "longitudinal_s_m": s_bucket,
                "radius_m": round(avg_r, 4),
                "deformation_percent": round(dev_pct, 2),
            }
        )

    notes.append(f"Deformation analysis computed over {len(sample_points)} surface sample points.")

    return Deformation3DMetrics(
        status=metric_status,
        nominal_diameter_mm=nominal_diameter_mm,
        nominal_radius_m=nominal_radius_m,
        mean_measured_radius_m=mean_r,
        min_radius_m=min_r,
        max_radius_m=max_r,
        max_radial_deviation_m=max_radial_dev,
        max_deformation_percent=max_def_pct,
        mean_deformation_percent=mean_def_pct,
        circularity_score=circularity,
        longitudinal_profile=tuple(longitudinal_profile),
        notes=tuple(notes),
    )
