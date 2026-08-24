"""Evaluation script for PipeVision Accuracy & Ground-Truth Validation (Phase 16).

Runs PipeVision accuracy evaluation on verified ground-truth dataset splits, compiling
and printing a reproducible MissionEvaluationReport JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2

from backend.app.services.evaluation.adapters import SewerMLAnnotationAdapter
from backend.app.services.evaluation.evaluator import PipeVisionEvaluator
from backend.app.services.evaluation.models import GroundTruthMission
from backend.app.services.inspection.models import (
    FusedInspectionObservation,
    SingleIngestionResult,
)
from backend.app.services.video.sewer_classifier import (
    SewerMLInferenceEngine,
    get_sewer_classifier_engine,
)


def run_sewer_ml_accuracy_evaluation(
    csv_path: str | Path = Path("approved-data/sewer-ml/splits/val.csv"),
    image_dir: str | Path = Path("approved-data/sewer-ml/images"),
    limit: int | None = None,
) -> dict:
    """Run accuracy evaluation of PipeVision Sewer-ML model against ground truth annotations."""
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"Ground truth CSV split file not found: {csv_file}")

    adapter = SewerMLAnnotationAdapter(csv_file)
    gt_frames = adapter.load_frames(limit=limit)
    gt_mission = GroundTruthMission(
        mission_id="SEWER-ML-VAL-EVAL",
        frames=gt_frames,
        source=f"Sewer-ML Split ({csv_file.name})",
    )

    # Attempt to load inference engine if weights exist
    engine: SewerMLInferenceEngine | None = None
    try:
        engine = get_sewer_classifier_engine()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[Warning] Could not initialize production Sewer-ML inference engine: {exc}")

    img_path_root = Path(image_dir)
    ingestion_results: list[SingleIngestionResult] = []

    for gt_frame in gt_frames:
        frame_filename = gt_frame.filename or f"{gt_frame.frame_id}.png"
        img_path = img_path_root / frame_filename

        # Search fallback paths if not directly in root
        if not img_path.is_file():
            img_path = img_path_root / "train00_subset" / frame_filename

        obs_list: list[FusedInspectionObservation] = []

        if engine is not None and img_path.is_file():
            image_bgr = cv2.imread(str(img_path))
            if image_bgr is not None:
                result = engine.predict(image_bgr)
                for dec in result.decisions:
                    if dec.detected:
                        obs_list.append(
                            FusedInspectionObservation(
                                observation_id=f"{gt_frame.frame_id}_{dec.class_code}",
                                mission_id="SEWER-ML-VAL-EVAL",
                                frame_index=gt_frame.frame_index or 0,
                                timestamp=None,
                                timestamp_iso=None,
                                distance_m=None,
                                frame_distance_m=None,
                                pose_distance_m=None,
                                distance_conflict_m=None,
                                robot_pose=None,
                                localization_quality="UNKNOWN",
                                class_code=dec.class_code,
                                confidence=dec.probability,
                                threshold=dec.threshold,
                                box=None,
                                model_name="Sewer-ML",
                                model_version=engine.model_version,
                                source_type="offline_image",
                            )
                        )

        ingestion_results.append(
            SingleIngestionResult(
                mission_id="SEWER-ML-VAL-EVAL",
                frame_id=gt_frame.frame_id,
                frame_index=gt_frame.frame_index or 0,
                timestamp_iso=None,
                source="photo",
                distance_m=gt_frame.true_distance_m,
                frame_path=str(img_path) if img_path.is_file() else None,
                observations=obs_list,
            )
        )

    evaluator = PipeVisionEvaluator()
    mission_report = evaluator.evaluate_mission(
        ground_truth_mission=gt_mission,
        ingestion_results=ingestion_results,
        model_name="SewerMLClassifier",
        model_version=engine.model_version if engine else "v1.0",
    )

    return mission_report.to_dict()


if __name__ == "__main__":
    report_dict = run_sewer_ml_accuracy_evaluation()
    print(json.dumps(report_dict, indent=2))
