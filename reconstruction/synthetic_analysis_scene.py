"""Synthetic 3D Condition Analysis Scene Generator & Accuracy Evaluator (Phase 16)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from reconstruction.analysis_models import (
    Pipe3DAnalysisReport,
)
from reconstruction.condition_analyzer import Pipe3DConditionAnalyzer
from reconstruction.defect_models import Projected3DDefect
from reconstruction.synthetic_defect_scene import SyntheticDefectSceneGenerator


class SyntheticAnalysisSceneGenerator:
    """Generates synthetic pipe condition scenes with known physical ground-truth metrics for validation."""

    def __init__(
        self,
        pipe_length_m: float = 10.0,
        pipe_diameter_mm: float = 300.0,
        frame_count: int = 21,
    ) -> None:
        self.pipe_length_m = pipe_length_m
        self.pipe_diameter_mm = pipe_diameter_mm
        self.frame_count = frame_count
        self.scene_gen = SyntheticDefectSceneGenerator(
            pipe_length_m=pipe_length_m,
            pipe_diameter_mm=pipe_diameter_mm,
            frame_count=frame_count,
        )

    def evaluate_analysis_accuracy(
        self,
        gt_s_m: float = 8.0,
        gt_theta_rad: float = 0.0,
        gt_length_m: float = 0.10,
        gt_width_m: float = 0.05,
    ) -> dict[str, Any]:
        """SYNTHETIC ALGORITHM VALIDATION ONLY: Evaluate 3D analysis accuracy against synthetic ground truth."""
        reconstruction = self.scene_gen.generate_reconstruction_output()
        obs, _gt_3d, rec_frame = self.scene_gen.generate_synthetic_defect(
            gt_longitudinal_s_m=gt_s_m,
            gt_angular_theta_rad=gt_theta_rad,
        )

        from reconstruction.defect_projector import Defect3DProjector

        projector = Defect3DProjector(default_pipe_diameter_mm=self.pipe_diameter_mm)
        proj_defect = projector.project_observation(
            observation=obs,
            frame=rec_frame,
            reconstruction=reconstruction,
            calibration=self.scene_gen.camera_calibration,
        )

        analyzer = Pipe3DConditionAnalyzer(section_length_m=1.0)
        report: Pipe3DAnalysisReport = analyzer.analyze_condition(
            reconstruction=reconstruction,
            defects=(proj_defect,),
            calibration=self.scene_gen.camera_calibration,
        )

        # Retrieve computed defect extent measurement
        meas = next(
            (m for m in report.defect_measurements if m.projection_id == proj_defect.projection_id),
            None,
        )

        s_error_m = 0.0
        if proj_defect.longitudinal_distance_m is not None:
            s_error_m = abs(proj_defect.longitudinal_distance_m - gt_s_m)

        return {
            "evaluation_label": "SYNTHETIC TEST SCENE ACCURACY",
            "ground_truth_status": "SYNTHETIC_GROUND_TRUTH_AVAILABLE",
            "synthetic_test_s_error_m": round(s_error_m, 6),
            "synthetic_test_analyzed_length_m": round(report.summary.analyzed_length_m, 3),
            "synthetic_test_defect_count": report.summary.total_defect_count,
            "synthetic_test_section_count": report.summary.section_count,
            "synthetic_test_condition_score": round(report.summary.overall_condition_score, 2),
            "measurement_status": meas.measurement_status.value if meas else "UNAVAILABLE",
        }

    @staticmethod
    def evaluate_real_data_compatibility(
        defects: Sequence[Projected3DDefect] | None = None,
    ) -> dict[str, Any]:
        """Real-data compatibility evaluator. Reports GROUND_TRUTH_UNAVAILABLE if ground truth is missing."""
        return {
            "evaluation_label": "REAL_DATA_COMPATIBILITY",
            "ground_truth_status": "GROUND_TRUTH_UNAVAILABLE",
            "notes": (
                "Real-world sensor data lacks verified metric 3D ground-truth coordinates; "
                "synthetic validation must not be substituted for real-world accuracy."
            ),
        }
