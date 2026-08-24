"""Domain Data Models for Advanced 3D Condition Analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from reconstruction.models import ScaleStatus


class MetricAvailabilityStatus(str, Enum):
    """Explicit availability status for physical 3D condition metrics."""

    ESTABLISHED = "ESTABLISHED"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class Defect3DMeasurement:
    """Dimensional and extent measurements for a projected 3D defect."""

    observation_id: str
    projection_id: str
    class_code: str
    measurement_status: MetricAvailabilityStatus
    length_m: float | None = None
    width_m: float | None = None
    area_m2: float | None = None
    longitudinal_span_m: float | None = None
    angular_span_rad: float | None = None
    depth_m: float | None = None
    depth_status: MetricAvailabilityStatus = MetricAvailabilityStatus.UNAVAILABLE
    confidence: float = 1.0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert measurement object to standard dictionary representation."""
        return {
            "observation_id": self.observation_id,
            "projection_id": self.projection_id,
            "class_code": self.class_code,
            "measurement_status": self.measurement_status.value,
            "length_m": round(self.length_m, 4) if self.length_m is not None else None,
            "width_m": round(self.width_m, 4) if self.width_m is not None else None,
            "area_m2": round(self.area_m2, 6) if self.area_m2 is not None else None,
            "longitudinal_span_m": (
                round(self.longitudinal_span_m, 4)
                if self.longitudinal_span_m is not None
                else None
            ),
            "angular_span_rad": (
                round(self.angular_span_rad, 4)
                if self.angular_span_rad is not None
                else None
            ),
            "depth_m": round(self.depth_m, 4) if self.depth_m is not None else None,
            "depth_status": self.depth_status.value,
            "confidence": round(self.confidence, 4),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class SpatialRelationship3D:
    """Spatial distance and proximity metrics between two projected defects."""

    source_projection_id: str
    target_projection_id: str
    longitudinal_distance_m: float
    angular_separation_rad: float
    euclidean_distance_3d_m: float | None
    is_same_section: bool
    euclidean_validity: MetricAvailabilityStatus = MetricAvailabilityStatus.UNAVAILABLE

    def to_dict(self) -> dict[str, Any]:
        """Convert spatial relationship object to dictionary format."""
        return {
            "source_projection_id": self.source_projection_id,
            "target_projection_id": self.target_projection_id,
            "longitudinal_distance_m": round(self.longitudinal_distance_m, 4),
            "angular_separation_rad": round(self.angular_separation_rad, 4),
            "euclidean_distance_3d_m": (
                round(self.euclidean_distance_3d_m, 4)
                if self.euclidean_distance_3d_m is not None
                else None
            ),
            "is_same_section": self.is_same_section,
            "euclidean_validity": self.euclidean_validity.value,
        }


@dataclass(frozen=True)
class Deformation3DMetrics:
    """Deformation, circularity, and diameter variation metrics along the 3D pipe."""

    status: MetricAvailabilityStatus
    nominal_diameter_mm: float
    nominal_radius_m: float
    mean_measured_radius_m: float | None = None
    min_radius_m: float | None = None
    max_radius_m: float | None = None
    max_radial_deviation_m: float | None = None
    max_deformation_percent: float | None = None
    mean_deformation_percent: float | None = None
    circularity_score: float | None = None
    longitudinal_profile: tuple[dict[str, float], ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert deformation metrics to dictionary format."""
        return {
            "status": self.status.value,
            "nominal_diameter_mm": round(self.nominal_diameter_mm, 2),
            "nominal_radius_m": round(self.nominal_radius_m, 4),
            "mean_measured_radius_m": (
                round(self.mean_measured_radius_m, 4)
                if self.mean_measured_radius_m is not None
                else None
            ),
            "min_radius_m": (
                round(self.min_radius_m, 4) if self.min_radius_m is not None else None
            ),
            "max_radius_m": (
                round(self.max_radius_m, 4) if self.max_radius_m is not None else None
            ),
            "max_radial_deviation_m": (
                round(self.max_radial_deviation_m, 4)
                if self.max_radial_deviation_m is not None
                else None
            ),
            "max_deformation_percent": (
                round(self.max_deformation_percent, 2)
                if self.max_deformation_percent is not None
                else None
            ),
            "mean_deformation_percent": (
                round(self.mean_deformation_percent, 2)
                if self.mean_deformation_percent is not None
                else None
            ),
            "circularity_score": (
                round(self.circularity_score, 4)
                if self.circularity_score is not None
                else None
            ),
            "longitudinal_profile_sample_count": len(self.longitudinal_profile),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class PipeSection3DCondition:
    """3D structural and defect condition metrics for a discrete section of pipe."""

    section_index: int
    start_distance_m: float
    end_distance_m: float
    section_length_m: float
    defect_count: int
    grouped_defect_count: int
    defect_density_per_m: float
    defect_area_density_m2_per_m: float
    dominant_class_codes: tuple[str, ...]
    condition_score: float
    deformation_metrics: Deformation3DMetrics
    scale_status: ScaleStatus
    coverage_ratio: float = 1.0
    quality_notes: tuple[str, ...] = field(default_factory=tuple)
    score_classification: str = "DERIVED_HEURISTIC_CONDITION_SCORE"
    scoring_formula_version: str = "Heuristic_v1"

    def to_dict(self) -> dict[str, Any]:
        """Convert section condition object to dictionary format."""
        return {
            "section_index": self.section_index,
            "start_distance_m": round(self.start_distance_m, 3),
            "end_distance_m": round(self.end_distance_m, 3),
            "section_length_m": round(self.section_length_m, 3),
            "defect_count": self.defect_count,
            "grouped_defect_count": self.grouped_defect_count,
            "defect_density_per_m": round(self.defect_density_per_m, 4),
            "defect_area_density_m2_per_m": round(self.defect_area_density_m2_per_m, 6),
            "dominant_class_codes": list(self.dominant_class_codes),
            "condition_score": round(self.condition_score, 2),
            "score_classification": self.score_classification,
            "scoring_formula_version": self.scoring_formula_version,
            "deformation": self.deformation_metrics.to_dict(),
            "scale_status": self.scale_status.value,
            "coverage_ratio": round(self.coverage_ratio, 3),
            "quality_notes": list(self.quality_notes),
        }


@dataclass(frozen=True)
class HeatmapProfile3D:
    """Structured machine-readable profile and spatial density data for visualization."""

    longitudinal_s_bins_m: tuple[float, ...]
    defect_counts: tuple[int, ...]
    defect_densities: tuple[float, ...]
    angular_theta_bins_rad: tuple[float, ...]
    angular_defect_counts: tuple[int, ...]
    deformation_percentages: tuple[float | None, ...]
    condition_scores: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert heatmap profile to standard dictionary representation."""
        return {
            "longitudinal_s_bins_m": [round(s, 3) for s in self.longitudinal_s_bins_m],
            "defect_counts": list(self.defect_counts),
            "defect_densities": [round(d, 4) for d in self.defect_densities],
            "angular_theta_bins_rad": [
                round(t, 4) for t in self.angular_theta_bins_rad
            ],
            "angular_defect_counts": list(self.angular_defect_counts),
            "deformation_percentages": [
                round(p, 2) if p is not None else None
                for p in self.deformation_percentages
            ],
            "condition_scores": [round(c, 2) for c in self.condition_scores],
        }


@dataclass(frozen=True)
class Pipe3DConditionSummary:
    """Overall mission-level 3D pipe condition summary."""

    mission_id: str
    total_reconstructed_length_m: float
    analyzed_length_m: float
    total_defect_count: int
    grouped_defect_count: int
    overall_condition_score: float
    mean_defect_density_per_m: float
    section_count: int
    scale_status: ScaleStatus
    deformation_summary: Deformation3DMetrics
    heatmap_profile: HeatmapProfile3D
    limitations: tuple[str, ...] = field(default_factory=tuple)
    score_classification: str = "DERIVED_HEURISTIC_CONDITION_SCORE"
    scoring_formula_version: str = "Heuristic_v1"

    def to_dict(self) -> dict[str, Any]:
        """Convert condition summary object to dictionary format."""
        return {
            "mission_id": self.mission_id,
            "total_reconstructed_length_m": round(self.total_reconstructed_length_m, 3),
            "analyzed_length_m": round(self.analyzed_length_m, 3),
            "total_defect_count": self.total_defect_count,
            "grouped_defect_count": self.grouped_defect_count,
            "overall_condition_score": round(self.overall_condition_score, 2),
            "score_classification": self.score_classification,
            "scoring_formula_version": self.scoring_formula_version,
            "mean_defect_density_per_m": round(self.mean_defect_density_per_m, 4),
            "section_count": self.section_count,
            "scale_status": self.scale_status.value,
            "deformation_summary": self.deformation_summary.to_dict(),
            "heatmap_profile": self.heatmap_profile.to_dict(),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class Pipe3DAnalysisReport:
    """Master structured report for Phase 25 3D Pipe Condition Analysis."""

    reconstruction_id: str
    mission_id: str
    analysis_version: str
    scale_status: ScaleStatus
    summary: Pipe3DConditionSummary
    sections: tuple[PipeSection3DCondition, ...]
    defect_measurements: tuple[Defect3DMeasurement, ...]
    spatial_relationships: tuple[SpatialRelationship3D, ...]
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert master report object to dictionary format."""
        return {
            "reconstruction_id": self.reconstruction_id,
            "mission_id": self.mission_id,
            "analysis_version": self.analysis_version,
            "scale_status": self.scale_status.value,
            "summary": self.summary.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "defect_measurements": [m.to_dict() for m in self.defect_measurements],
            "spatial_relationships": [r.to_dict() for r in self.spatial_relationships],
            "limitations": list(self.limitations),
        }
