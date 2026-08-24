"""3D Pipe Section Condition, Defect Density, and Mission Condition Analyzer (Phase 25)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import ClassVar

from morphology.models import MorphologySummaryReport
from reconstruction.analysis_models import (
    Defect3DMeasurement,
    HeatmapProfile3D,
    Pipe3DAnalysisReport,
    Pipe3DConditionSummary,
    PipeSection3DCondition,
)
from reconstruction.calibration import CameraCalibration
from reconstruction.defect_clustering import MultiFrameDefectAssociator
from reconstruction.defect_extent import (
    compute_defect_extent,
    compute_spatial_relationships,
)
from reconstruction.defect_models import (
    Grouped3DDefect,
    Projected3DDefect,
)
from reconstruction.deformation_analyzer import analyze_pipe_deformation
from reconstruction.models import Reconstruction3DOutput, ScaleStatus


class Pipe3DConditionAnalyzer:
    """Core engine for 3D section partitioning, density calculation, condition scoring, and report generation."""

    SEVERITY_WEIGHTS: ClassVar[dict[str, float]] = {
        "CR": 10.0,  # Crack
        "BS": 12.0,  # Broken / Fractured Pipe
        "DE": 10.0,  # Debris / Deposit
        "OS": 10.0,  # Obstacle
        "VC": 8.0,   # Void / Cavity
        "SA": 5.0,   # Surface Damage / Abrasion
    }

    def __init__(self, section_length_m: float = 1.0) -> None:
        self.section_length_m = max(0.25, section_length_m)

    def calculate_section_condition_score(
        self,
        grouped_defect_count: int,
        defect_area_m2_total: float,
        section_length_m: float,
        class_codes: Sequence[str],
        deformation_percent: float | None = None,
    ) -> float:
        """Calculate DERIVED HEURISTIC condition score (0 to 100) for a section of pipe.

        CLASSIFICATION: DERIVED_HEURISTIC_CONDITION_SCORE (Formula Version: Heuristic_v1)
        LIMITATION: This score is a heuristic visual/geometric penalty model and must NOT
        be presented as a certified civil engineering asset risk grade or standard.

        Formula:
            Score = max(0.0, 100.0 - (P_density + P_severity + P_deformation))
        where:
            P_density = min(40.0, (grouped_defect_density * 15.0) + (area_density * 50.0))
            P_severity = min(40.0, sum(SEVERITY_WEIGHTS[code] for code in class_codes))
            P_deformation = min(30.0, deformation_percent * 2.0) if deformation_percent else 0.0
        """
        density_per_m = grouped_defect_count / max(0.1, section_length_m)
        area_density_per_m = defect_area_m2_total / max(0.1, section_length_m)

        p_density = min(40.0, (density_per_m * 15.0) + (area_density_per_m * 50.0))

        p_severity_raw = sum(
            self.SEVERITY_WEIGHTS.get(code.upper(), 5.0) for code in class_codes
        )
        p_severity = min(40.0, p_severity_raw)

        p_deformation = 0.0
        if deformation_percent is not None and deformation_percent > 0.0:
            p_deformation = min(30.0, deformation_percent * 2.0)

        score = max(0.0, 100.0 - (p_density + p_severity + p_deformation))
        return round(score, 2)

    def analyze_condition(
        self,
        reconstruction: Reconstruction3DOutput | None,
        defects: Sequence[Projected3DDefect],
        grouped_defects: Sequence[Grouped3DDefect] | None = None,
        morphology_summary: MorphologySummaryReport | None = None,
        calibration: CameraCalibration | None = None,
    ) -> Pipe3DAnalysisReport:
        """Perform comprehensive Phase 25 3D condition analysis and output master report."""
        mission_id = reconstruction.mission_id if reconstruction else "unknown_mission"
        reconstruction_id = (
            reconstruction.reconstruction_id if reconstruction else "no_reconstruction"
        )
        scale_status = (
            reconstruction.scale_status if reconstruction else ScaleStatus.UNAVAILABLE
        )
        default_pipe_diameter_mm = (
            reconstruction.baseline_diameter_mm
            if reconstruction and reconstruction.baseline_diameter_mm is not None
            else 300.0
        )

        limitations: list[str] = [
            (
                "Condition score is classified as DERIVED_HEURISTIC_CONDITION_SCORE (Heuristic_v1) "
                "and does not constitute a certified civil infrastructure asset rating."
            )
        ]
        if scale_status == ScaleStatus.UNAVAILABLE:
            limitations.append(
                "Metric scale is UNAVAILABLE; absolute spatial measurements and deformation percentages are uncalibrated."
            )
        if reconstruction is None:
            limitations.append("No 3D pipe reconstruction geometry provided; analysis degraded to 2D observation track.")

        # 1. Multi-frame association grouping to prevent double-counting physical defects
        if grouped_defects is None and defects:
            associator = MultiFrameDefectAssociator()
            grouped_defects = associator.cluster_projections(tuple(defects))
        elif grouped_defects is None:
            grouped_defects = ()

        # 2. Defect 3D measurements and extents
        defect_measurements: list[Defect3DMeasurement] = [
            compute_defect_extent(
                d, calibration=calibration, default_pipe_diameter_mm=default_pipe_diameter_mm
            )
            for d in defects
        ]

        # 3. Pairwise spatial relationships
        spatial_relationships = compute_spatial_relationships(
            defects,
            default_pipe_diameter_mm=default_pipe_diameter_mm,
            section_length_m=self.section_length_m,
        )

        # 4. Deformation analysis
        deformation_summary = analyze_pipe_deformation(
            reconstruction, morphology_summary=morphology_summary
        )

        # 5. Section partitioning & analysis (Deterministic boundary handling)
        total_length_m = 0.0
        if reconstruction and reconstruction.centerline:
            total_length_m = reconstruction.centerline.total_length_m
        elif defects:
            valid_s = [
                d.longitudinal_distance_m
                for d in defects
                if d.longitudinal_distance_m is not None
            ]
            total_length_m = max(valid_s) if valid_s else 0.0

        analyzed_length_m = max(0.1, total_length_m)
        num_sections = max(1, math.ceil(analyzed_length_m / self.section_length_m))

        sections: list[PipeSection3DCondition] = []
        longitudinal_s_bins: list[float] = []
        sec_defect_counts: list[int] = []
        sec_defect_densities: list[float] = []
        sec_def_percents: list[float | None] = []
        sec_condition_scores: list[float] = []

        for sec_idx in range(num_sections):
            sec_start = sec_idx * self.section_length_m
            sec_end = min(analyzed_length_m, (sec_idx + 1) * self.section_length_m)
            actual_sec_len = max(0.1, sec_end - sec_start)
            is_last = (sec_idx == num_sections - 1)

            # Raw defects in section
            sec_raw_defects = [
                d
                for d in defects
                if d.longitudinal_distance_m is not None
                and (
                    (sec_start <= d.longitudinal_distance_m <= sec_end + 1e-6)
                    if is_last
                    else (sec_start <= d.longitudinal_distance_m < sec_end)
                )
            ]
            # Grouped defects in section
            sec_grouped_defects = [
                g
                for g in grouped_defects
                if (
                    (sec_start <= g.mean_longitudinal_distance_m <= sec_end + 1e-6)
                    if is_last
                    else (sec_start <= g.mean_longitudinal_distance_m < sec_end)
                )
            ]

            # Section defect density
            grp_count = len(sec_grouped_defects)
            raw_count = len(sec_raw_defects)
            density_per_m = grp_count / actual_sec_len

            # Section defect area density
            sec_meas = [
                m
                for m in defect_measurements
                if any(d.observation_id == m.observation_id for d in sec_raw_defects)
            ]
            total_area_m2 = sum(m.area_m2 for m in sec_meas if m.area_m2 is not None)
            area_density_per_m = total_area_m2 / actual_sec_len

            # Class frequencies & dominant codes
            class_counts: dict[str, int] = {}
            for d in sec_raw_defects:
                class_counts[d.class_code] = class_counts.get(d.class_code, 0) + 1
            dominant_classes = tuple(
                sorted(class_counts.keys(), key=lambda c: class_counts[c], reverse=True)[:3]
            )

            # Section deformation
            sec_def_pct: float | None = None
            if deformation_summary.longitudinal_profile:
                prof_samples = [
                    p["deformation_percent"]
                    for p in deformation_summary.longitudinal_profile
                    if (
                        (sec_start <= p["longitudinal_s_m"] <= sec_end + 1e-6)
                        if is_last
                        else (sec_start <= p["longitudinal_s_m"] < sec_end)
                    )
                ]
                if prof_samples:
                    sec_def_pct = max(prof_samples)

            sec_score = self.calculate_section_condition_score(
                grouped_defect_count=grp_count,
                defect_area_m2_total=total_area_m2,
                section_length_m=actual_sec_len,
                class_codes=[d.class_code for d in sec_raw_defects],
                deformation_percent=sec_def_pct,
            )

            sec_notes: list[str] = []
            if raw_count > grp_count:
                sec_notes.append(
                    f"Multi-frame association linked {raw_count} 2D observations into {grp_count} distinct physical defects."
                )

            sections.append(
                PipeSection3DCondition(
                    section_index=sec_idx,
                    start_distance_m=sec_start,
                    end_distance_m=sec_end,
                    section_length_m=actual_sec_len,
                    defect_count=raw_count,
                    grouped_defect_count=grp_count,
                    defect_density_per_m=density_per_m,
                    defect_area_density_m2_per_m=area_density_per_m,
                    dominant_class_codes=dominant_classes,
                    condition_score=sec_score,
                    deformation_metrics=deformation_summary,
                    scale_status=scale_status,
                    coverage_ratio=1.0,
                    quality_notes=tuple(sec_notes),
                    score_classification="DERIVED_HEURISTIC_CONDITION_SCORE",
                    scoring_formula_version="Heuristic_v1",
                )
            )

            longitudinal_s_bins.append(sec_start + (actual_sec_len / 2.0))
            sec_defect_counts.append(grp_count)
            sec_defect_densities.append(density_per_m)
            sec_def_percents.append(sec_def_pct)
            sec_condition_scores.append(sec_score)

        # 6. Angular theta histogram bins (8 clock quadrants: 0, 45, 90, 135, 180, 225, 270, 315 deg)
        angular_bins_rad = tuple((i * math.pi / 4.0) for i in range(8))
        angular_counts = [0] * 8
        for d in defects:
            if d.angular_position_rad is not None:
                ang = d.angular_position_rad % (2.0 * math.pi)
                quad_idx = int(((ang + (math.pi / 8.0)) % (2.0 * math.pi)) / (math.pi / 4.0)) % 8
                angular_counts[quad_idx] += 1

        heatmap_profile = HeatmapProfile3D(
            longitudinal_s_bins_m=tuple(longitudinal_s_bins),
            defect_counts=tuple(sec_defect_counts),
            defect_densities=tuple(sec_defect_densities),
            angular_theta_bins_rad=angular_bins_rad,
            angular_defect_counts=tuple(angular_counts),
            deformation_percentages=tuple(sec_def_percents),
            condition_scores=tuple(sec_condition_scores),
        )

        # 7. Summary metrics
        overall_score = (
            sum(sec_condition_scores) / len(sec_condition_scores)
            if sec_condition_scores
            else 100.0
        )
        total_grp_count = len(grouped_defects)
        mean_density = total_grp_count / analyzed_length_m if analyzed_length_m > 0 else 0.0

        summary = Pipe3DConditionSummary(
            mission_id=mission_id,
            total_reconstructed_length_m=total_length_m,
            analyzed_length_m=analyzed_length_m,
            total_defect_count=len(defects),
            grouped_defect_count=total_grp_count,
            overall_condition_score=overall_score,
            mean_defect_density_per_m=mean_density,
            section_count=len(sections),
            scale_status=scale_status,
            deformation_summary=deformation_summary,
            heatmap_profile=heatmap_profile,
            limitations=tuple(limitations),
            score_classification="DERIVED_HEURISTIC_CONDITION_SCORE",
            scoring_formula_version="Heuristic_v1",
        )

        return Pipe3DAnalysisReport(
            reconstruction_id=reconstruction_id,
            mission_id=mission_id,
            analysis_version="Phase25_v1",
            scale_status=scale_status,
            summary=summary,
            sections=tuple(sections),
            defect_measurements=tuple(defect_measurements),
            spatial_relationships=tuple(spatial_relationships),
            limitations=tuple(limitations),
        )
