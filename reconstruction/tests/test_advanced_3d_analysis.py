"""Comprehensive Test Suite for Phase 25 Advanced 3D Pipe Condition Analysis."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

# Ensure backend orchestrator is loaded before domain modules to prevent circular package init cycles
import backend.app.services.mission.orchestrator  # noqa: F401
from digital_twin.models import DigitalTwinState, SynchronizationStatus
from mapping.models import MapObservation, PipeInspectionMap
from reconstruction.analysis_models import (
    MetricAvailabilityStatus,
)
from reconstruction.condition_analyzer import Pipe3DConditionAnalyzer
from reconstruction.defect_extent import (
    compute_defect_extent,
    compute_spatial_relationships,
)
from reconstruction.defect_models import (
    Defect3DFootprint,
    Projected3DDefect,
    ProjectionStatus,
    Source2DGeometry,
)
from reconstruction.defect_projector import Defect3DProjector
from reconstruction.deformation_analyzer import analyze_pipe_deformation
from reconstruction.integration import (
    associate_advanced_3d_analysis_with_digital_twin,
    associate_advanced_3d_analysis_with_mapping,
)
from reconstruction.models import Point3D, ScaleStatus
from reconstruction.synthetic_analysis_scene import SyntheticAnalysisSceneGenerator
from reconstruction.synthetic_defect_scene import SyntheticDefectSceneGenerator


def test_defect_extent_and_surface_metrics() -> None:
    fp = Defect3DFootprint(
        center_3d=Point3D(x=5.1, y=0.0, z=0.15),
        extent_type="PROJECTED_EXTENT_ESTIMATE",
        longitudinal_span_m=0.2,
        angular_span_rad=0.2,
    )
    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    proj = Projected3DDefect(
        projection_id="p_test1",
        observation_id="obs_1",
        mission_id="m1",
        class_code="CR",
        ai_confidence=0.95,
        projection_confidence=0.90,
        source_2d_geometry=src_geom,
        footprint_3d=fp,
        point_3d=Point3D(x=5.1, y=0.0, z=0.15),
        longitudinal_distance_m=5.1,
        angular_position_rad=0.1,
        radial_position_m=0.15,
        scale_status=ScaleStatus.ESTABLISHED,
        quality_state=ProjectionStatus.VALID,
    )

    meas = compute_defect_extent(proj, default_pipe_diameter_mm=300.0)
    assert meas.measurement_status == MetricAvailabilityStatus.ESTABLISHED
    assert meas.longitudinal_span_m is not None
    assert math.isclose(meas.longitudinal_span_m, 0.2, abs_tol=1e-4)
    assert meas.angular_span_rad is not None
    assert math.isclose(meas.angular_span_rad, 0.2, abs_tol=1e-4)
    assert meas.area_m2 is not None
    assert math.isclose(meas.area_m2, 0.2 * (0.2 * 0.15), abs_tol=1e-4)
    # Honest depth state: no metric radial deformation observed -> UNAVAILABLE
    assert meas.depth_status == MetricAvailabilityStatus.UNAVAILABLE
    assert meas.depth_m is None


def test_missing_data_honest_metric_states() -> None:
    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    proj_bad = Projected3DDefect(
        projection_id="p_bad",
        observation_id="obs_bad",
        mission_id="m1",
        class_code="CR",
        ai_confidence=0.8,
        projection_confidence=0.0,
        source_2d_geometry=src_geom,
        scale_status=ScaleStatus.UNAVAILABLE,
        quality_state=ProjectionStatus.INSUFFICIENT_DATA,
        failure_reason="Isolated photo missing pose and calibration",
        point_3d=None,
        longitudinal_distance_m=None,
        angular_position_rad=None,
        radial_position_m=None,
    )

    meas = compute_defect_extent(proj_bad, default_pipe_diameter_mm=300.0)
    assert meas.measurement_status == MetricAvailabilityStatus.UNAVAILABLE
    assert meas.length_m is None
    assert meas.area_m2 is None
    assert meas.depth_status == MetricAvailabilityStatus.UNAVAILABLE


def test_spatial_relationships() -> None:
    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    p1 = Projected3DDefect(
        projection_id="p1",
        observation_id="obs_1",
        mission_id="m1",
        class_code="CR",
        ai_confidence=0.9,
        projection_confidence=0.9,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=2.0, y=0.0, z=0.15),
        longitudinal_distance_m=2.0,
        angular_position_rad=0.0,
        scale_status=ScaleStatus.ESTABLISHED,
        quality_state=ProjectionStatus.VALID,
        radial_position_m=0.15,
    )
    p2 = Projected3DDefect(
        projection_id="p2",
        observation_id="obs_2",
        mission_id="m1",
        class_code="CR",
        ai_confidence=0.9,
        projection_confidence=0.9,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=5.0, y=0.0, z=0.15),
        longitudinal_distance_m=5.0,
        angular_position_rad=0.0,
        scale_status=ScaleStatus.ESTABLISHED,
        quality_state=ProjectionStatus.VALID,
        radial_position_m=0.15,
    )

    rels = compute_spatial_relationships((p1, p2), default_pipe_diameter_mm=300.0, section_length_m=1.0)
    assert len(rels) == 1
    rel = rels[0]
    assert math.isclose(rel.longitudinal_distance_m, 3.0, abs_tol=1e-4)
    assert math.isclose(rel.angular_separation_rad, 0.0, abs_tol=1e-4)
    assert rel.euclidean_distance_3d_m is not None
    assert math.isclose(rel.euclidean_distance_3d_m, 3.0, abs_tol=1e-4)
    assert rel.is_same_section is False


def test_grouped_defect_deduplication_5_frames() -> None:
    """Verify 5 observation frames of the same physical defect count as 1 physical defect."""
    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    multi_frame_defects: list[Projected3DDefect] = []

    for f_idx in range(5):
        d = Projected3DDefect(
            projection_id=f"p_frame_{f_idx}",
            observation_id=f"obs_frame_{f_idx}",
            mission_id="m_dedup",
            class_code="CR",
            ai_confidence=0.9,
            projection_confidence=0.95,
            source_2d_geometry=src_geom,
            point_3d=Point3D(x=3.0, y=0.0, z=0.15),
            longitudinal_distance_m=3.00 + (f_idx * 0.01),  # Slightly different frame poses
            angular_position_rad=0.0,
            radial_position_m=0.15,
            scale_status=ScaleStatus.ESTABLISHED,
            quality_state=ProjectionStatus.VALID,
        )
        multi_frame_defects.append(d)

    analyzer = Pipe3DConditionAnalyzer(section_length_m=1.0)
    report = analyzer.analyze_condition(
        reconstruction=None,
        defects=tuple(multi_frame_defects),
    )

    assert report.summary.total_defect_count == 5  # 5 raw 2D observations
    assert report.summary.grouped_defect_count == 1  # Grouped into 1 physical defect
    assert report.summary.score_classification == "DERIVED_HEURISTIC_CONDITION_SCORE"


def test_section_boundary_determinism() -> None:
    """Verify defects on section boundaries are deterministically placed without double counting or dropping."""
    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    d_exact_boundary = Projected3DDefect(
        projection_id="p_boundary",
        observation_id="obs_boundary",
        mission_id="m_bound",
        class_code="CR",
        ai_confidence=0.9,
        projection_confidence=0.95,
        source_2d_geometry=src_geom,
        point_3d=Point3D(x=2.0, y=0.0, z=0.15),
        longitudinal_distance_m=2.0,  # Boundary at s=2.0 m
        angular_position_rad=0.0,
        radial_position_m=0.15,
        scale_status=ScaleStatus.ESTABLISHED,
        quality_state=ProjectionStatus.VALID,
    )

    analyzer = Pipe3DConditionAnalyzer(section_length_m=1.0)
    report = analyzer.analyze_condition(
        reconstruction=None,
        defects=(d_exact_boundary,),
    )

    # 2 sections for s=2.0m: [0, 1.0) and [1.0, 2.0]
    total_defects_in_sections = sum(s.defect_count for s in report.sections)
    assert total_defects_in_sections == 1
    assert len(report.sections) == 2
    assert report.sections[0].defect_count == 0
    assert report.sections[1].defect_count == 1


def test_deformation_analysis() -> None:
    scene_gen = SyntheticDefectSceneGenerator(pipe_length_m=10.0, pipe_diameter_mm=300.0)
    reconstruction = scene_gen.generate_reconstruction_output()

    def_metrics = analyze_pipe_deformation(reconstruction)
    assert def_metrics.status == MetricAvailabilityStatus.ESTABLISHED
    assert def_metrics.nominal_diameter_mm == 300.0
    assert def_metrics.mean_measured_radius_m is not None
    assert math.isclose(def_metrics.mean_measured_radius_m, 0.15, abs_tol=1e-3)
    assert def_metrics.max_deformation_percent is not None
    assert def_metrics.max_deformation_percent < 1.0
    assert def_metrics.circularity_score is not None
    assert def_metrics.circularity_score > 0.95


def test_section_condition_and_density_analysis() -> None:
    scene_gen = SyntheticDefectSceneGenerator(pipe_length_m=10.0, pipe_diameter_mm=300.0)
    reconstruction = scene_gen.generate_reconstruction_output()

    obs, _gt_3d, rec_frame = scene_gen.generate_synthetic_defect(
        gt_longitudinal_s_m=3.5, gt_angular_theta_rad=0.0
    )
    projector = Defect3DProjector(default_pipe_diameter_mm=300.0)
    proj_defect = projector.project_observation(
        observation=obs,
        frame=rec_frame,
        reconstruction=reconstruction,
        calibration=scene_gen.camera_calibration,
    )

    analyzer = Pipe3DConditionAnalyzer(section_length_m=1.0)
    report = analyzer.analyze_condition(
        reconstruction=reconstruction,
        defects=(proj_defect,),
        calibration=scene_gen.camera_calibration,
    )

    assert report.summary.total_defect_count == 1
    assert report.summary.grouped_defect_count == 1
    assert report.summary.section_count == 10
    assert report.summary.score_classification == "DERIVED_HEURISTIC_CONDITION_SCORE"
    # Section at s=3.5 (index 3) should contain the defect
    sec_3 = report.sections[3]
    assert sec_3.defect_count == 1
    assert sec_3.grouped_defect_count == 1
    assert sec_3.defect_density_per_m == 1.0
    assert sec_3.condition_score < 100.0
    # Pristine section at s=0.0 (index 0) should have score = 100.0
    assert report.sections[0].condition_score == 100.0


def test_digital_twin_and_mapping_bridges() -> None:
    syn_analyzer = SyntheticAnalysisSceneGenerator(pipe_length_m=5.0, pipe_diameter_mm=300.0)
    eval_res = syn_analyzer.evaluate_analysis_accuracy(gt_s_m=2.5)

    assert eval_res["evaluation_label"] == "SYNTHETIC TEST SCENE ACCURACY"
    assert eval_res["ground_truth_status"] == "SYNTHETIC_GROUND_TRUTH_AVAILABLE"

    scene_gen = syn_analyzer.scene_gen
    reconstruction = scene_gen.generate_reconstruction_output()
    obs, _gt_3d, rec_frame = scene_gen.generate_synthetic_defect(gt_longitudinal_s_m=2.5)
    projector = Defect3DProjector()
    proj = projector.project_observation(
        observation=obs,
        frame=rec_frame,
        reconstruction=reconstruction,
        calibration=scene_gen.camera_calibration,
    )

    analyzer = Pipe3DConditionAnalyzer()
    report = analyzer.analyze_condition(
        reconstruction=reconstruction,
        defects=(proj,),
        calibration=scene_gen.camera_calibration,
    )

    # 1. Digital Twin additive bridge
    twin_state = DigitalTwinState(
        robot_id="r1",
        mission_id="m1",
        last_updated_at=datetime.now(timezone.utc),
        synchronization_status=SynchronizationStatus.SYNCHRONIZED.value,
        robot_state=None,
        mission_state=None,
    )
    twin_dict = associate_advanced_3d_analysis_with_digital_twin(twin_state, report)
    assert "advanced_3d_analysis" in twin_dict
    assert twin_dict["advanced_3d_analysis"]["analysis_version"] == "Phase25_v1"

    # 2. Mapping additive bridge
    map_obs = MapObservation(
        observation_id="obs_1",
        mission_id="m1",
        frame_index=0,
        timestamp=datetime.now(timezone.utc),
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        distance_m=2.5,
        x=2.5,
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
        mission_id="m1",
        total_inspected_distance_m=5.0,
        start_distance_m=0.0,
        end_distance_m=5.0,
        observation_count=1,
        observations=(map_obs,),
    )
    map_dict = associate_advanced_3d_analysis_with_mapping(pipe_map, report)
    assert "advanced_3d_analysis" in map_dict
    assert map_dict["advanced_3d_analysis"]["overall_condition_score"] is not None


def test_performance_bounded_500_defects_benchmark() -> None:
    """Benchmark test on synthetic workload (500 defects).

    LABEL: SYNTHETIC_WORKLOAD_BENCHMARK (Environment Dependent).
    This benchmark measures Python algorithmic efficiency in synthetic memory workloads.
    """
    src_geom = Source2DGeometry(center_pixel=(960.0, 540.0))
    defects: list[Projected3DDefect] = []

    for i in range(500):
        s_m = (i % 50) * 0.2
        d = Projected3DDefect(
            projection_id=f"p_perf_{i}",
            observation_id=f"obs_perf_{i}",
            mission_id="m_perf",
            class_code="CR" if i % 2 == 0 else "SA",
            ai_confidence=0.9,
            projection_confidence=0.95,
            source_2d_geometry=src_geom,
            point_3d=Point3D(x=s_m, y=0.0, z=0.15),
            longitudinal_distance_m=s_m,
            angular_position_rad=(i % 8) * (math.pi / 4.0),
            radial_position_m=0.15,
            scale_status=ScaleStatus.ESTABLISHED,
            quality_state=ProjectionStatus.VALID,
        )
        defects.append(d)

    analyzer = Pipe3DConditionAnalyzer(section_length_m=1.0)
    t0 = time.perf_counter()
    report = analyzer.analyze_condition(
        reconstruction=None,
        defects=tuple(defects),
    )
    elapsed_sec = time.perf_counter() - t0

    assert report.summary.total_defect_count == 500
    # 500 defects should analyze sub-second (< 1.5s in test environment)
    assert elapsed_sec < 1.5
