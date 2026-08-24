"""Core Accuracy Evaluation Engine for PipeVision.

Calculates detection, multi-label classification, confidence calibration (ECE),
localization longitudinal error, morphology error, defect spatial matching, error taxonomy breakdown,
and mission-level validation metrics with strict mathematical honesty and reproducibility.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.evaluation.models import (
    CalibrationBin,
    CalibrationReport,
    ClassificationMetricsReport,
    ClassMetricSummary,
    DefectLocationMetricsReport,
    DetectionMetricsReport,
    ErrorTaxonomy,
    GroundTruthFrame,
    GroundTruthMission,
    LocalizationMetricsReport,
    MetricAvailability,
    MissionEvaluationReport,
    MorphologyMetricsReport,
)
from backend.app.services.inspection.models import (
    BoundingBox,
    FusedInspectionObservation,
    SingleIngestionResult,
)
from backend.app.services.video.sewer_dataset import DEFECT_CLASSES


def calculate_iou(box1: BoundingBox, box2: BoundingBox) -> float:
    """Calculate Intersection over Union (IoU) between two 2D bounding boxes."""
    x_inter1 = max(box1.x1, box2.x1)
    y_inter1 = max(box1.y1, box2.y1)
    x_inter2 = min(box1.x2, box2.x2)
    y_inter2 = min(box1.y2, box2.y2)

    inter_width = max(0.0, x_inter2 - x_inter1)
    inter_height = max(0.0, y_inter2 - y_inter1)
    area_inter = inter_width * inter_height

    area1 = max(0.0, box1.x2 - box1.x1) * max(0.0, box1.y2 - box1.y1)
    area2 = max(0.0, box2.x2 - box2.x1) * max(0.0, box2.y2 - box2.y1)

    area_union = area1 + area2 - area_inter
    if area_union <= 0.0:
        return 0.0

    return area_inter / area_union


class PipeVisionEvaluator:
    """Deterministic evaluation engine for PipeVision accuracy and error metrics."""

    def __init__(
        self,
        iou_threshold: float = 0.5,
        spatial_tolerance_m: float = 1.0,
        min_support_threshold: int = 5,
        random_seed: int = 42,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.spatial_tolerance_m = spatial_tolerance_m
        self.min_support_threshold = min_support_threshold
        self.random_seed = random_seed

    def evaluate_detection(
        self,
        paired_frames: Sequence[tuple[GroundTruthFrame, list[FusedInspectionObservation]]],
        class_vocabulary: list[str] | None = None,
    ) -> DetectionMetricsReport:
        """Evaluate 2D bounding box detection metrics using IoU matching."""
        vocab = class_vocabulary if class_vocabulary is not None else DEFECT_CLASSES
        total_gt_boxes = 0
        total_pred_boxes = 0
        has_any_gt_box = False

        tp_per_class: dict[str, int] = defaultdict(int)
        fp_per_class: dict[str, int] = defaultdict(int)
        fn_per_class: dict[str, int] = defaultdict(int)
        gt_support_per_class: dict[str, int] = defaultdict(int)

        for gt_frame, obs_list in paired_frames:
            # Gather GT boxes
            gt_boxes_by_class: dict[str, list[BoundingBox]] = defaultdict(list)
            for d in gt_frame.defects:
                if d.box is not None:
                    has_any_gt_box = True
                    gt_boxes_by_class[d.class_code].append(d.box)
                    gt_support_per_class[d.class_code] += 1
                    total_gt_boxes += 1

            # Gather Pred boxes
            pred_boxes_by_class: dict[str, list[BoundingBox]] = defaultdict(list)
            for obs in obs_list:
                if obs.box is not None:
                    pred_boxes_by_class[obs.class_code].append(obs.box)
                    total_pred_boxes += 1

            # Match per class
            for cls_code in set(gt_boxes_by_class.keys()).union(pred_boxes_by_class.keys()):
                gt_b_list = list(gt_boxes_by_class[cls_code])
                pred_b_list = list(pred_boxes_by_class[cls_code])
                matched_gt_indices: set[int] = set()

                for p_box in pred_b_list:
                    best_iou = 0.0
                    best_gt_idx = -1
                    for gt_idx, g_box in enumerate(gt_b_list):
                        if gt_idx in matched_gt_indices:
                            continue
                        iou = calculate_iou(p_box, g_box)
                        if iou > best_iou:
                            best_iou = iou
                            best_gt_idx = gt_idx

                    if best_iou >= self.iou_threshold and best_gt_idx >= 0:
                        tp_per_class[cls_code] += 1
                        matched_gt_indices.add(best_gt_idx)
                    else:
                        fp_per_class[cls_code] += 1

                fn_per_class[cls_code] += len(gt_b_list) - len(matched_gt_indices)

        if not has_any_gt_box:
            return DetectionMetricsReport(
                status=MetricAvailability.UNAVAILABLE,
                iou_threshold=self.iou_threshold,
                total_evaluated_frames=len(paired_frames),
                total_ground_truth_boxes=0,
                total_predicted_boxes=total_pred_boxes,
                true_positives=0,
                false_positives=total_pred_boxes,
                false_negatives=0,
                precision=0.0,
                recall=0.0,
                f1=0.0,
                reason_if_unavailable="unavailable — no ground truth bounding box annotations exist in dataset",
            )

        total_tp = sum(tp_per_class.values())
        total_fp = sum(fp_per_class.values())
        total_fn = sum(fn_per_class.values())

        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        f1 = (2.0 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        per_class_summary: dict[str, ClassMetricSummary] = {}
        for cls_code in vocab:
            tp = tp_per_class[cls_code]
            fp = fp_per_class[cls_code]
            fn = fn_per_class[cls_code]
            supp = gt_support_per_class[cls_code]

            p_c = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r_c = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_c = (2.0 * p_c * r_c) / (p_c + r_c) if (p_c + r_c) > 0 else 0.0

            status = (
                MetricAvailability.AVAILABLE
                if supp >= self.min_support_threshold
                else MetricAvailability.INSUFFICIENT_SUPPORT
            )

            per_class_summary[cls_code] = ClassMetricSummary(
                class_code=cls_code,
                precision=p_c,
                recall=r_c,
                f1=f1_c,
                support=supp,
                negative_support=max(0, len(paired_frames) - supp),
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                true_negatives=max(0, len(paired_frames) - tp - fp - fn),
                status=status,
                note=None if status == MetricAvailability.AVAILABLE else "insufficient sample size",
            )

        return DetectionMetricsReport(
            status=MetricAvailability.AVAILABLE,
            iou_threshold=self.iou_threshold,
            total_evaluated_frames=len(paired_frames),
            total_ground_truth_boxes=total_gt_boxes,
            total_predicted_boxes=total_pred_boxes,
            true_positives=total_tp,
            false_positives=total_fp,
            false_negatives=total_fn,
            precision=precision,
            recall=recall,
            f1=f1,
            per_class_metrics=per_class_summary,
        )

    def evaluate_classification(
        self,
        paired_frames: Sequence[tuple[GroundTruthFrame, list[FusedInspectionObservation]]],
        class_vocabulary: list[str] | None = None,
    ) -> ClassificationMetricsReport:
        """Evaluate multi-label classification performance across frames."""
        vocab = class_vocabulary if class_vocabulary is not None else DEFECT_CLASSES
        total_frames = len(paired_frames)

        if total_frames == 0:
            return ClassificationMetricsReport(
                status=MetricAvailability.UNAVAILABLE,
                total_evaluated_frames=0,
                macro_precision=0.0,
                macro_recall=0.0,
                macro_f1=0.0,
                micro_precision=0.0,
                micro_recall=0.0,
                micro_f1=0.0,
                exact_match_ratio=0.0,
                reason_if_unavailable="unavailable — no evaluation frames provided",
            )

        tp_per_class: dict[str, int] = defaultdict(int)
        fp_per_class: dict[str, int] = defaultdict(int)
        fn_per_class: dict[str, int] = defaultdict(int)
        tn_per_class: dict[str, int] = defaultdict(int)
        gt_pos_per_class: dict[str, int] = defaultdict(int)

        exact_matches = 0

        for gt_frame, obs_list in paired_frames:
            # Build GT set
            gt_classes: set[str] = set()
            for cls_code in vocab:
                if gt_frame.presence.get(cls_code, False):
                    gt_classes.add(cls_code)
            for d in gt_frame.defects:
                gt_classes.add(d.class_code)

            # Build Pred set
            pred_classes: set[str] = {obs.class_code for obs in obs_list}

            if gt_classes == pred_classes:
                exact_matches += 1

            for cls_code in vocab:
                is_gt = cls_code in gt_classes
                is_pred = cls_code in pred_classes

                if is_gt:
                    gt_pos_per_class[cls_code] += 1

                if is_gt and is_pred:
                    tp_per_class[cls_code] += 1
                elif not is_gt and is_pred:
                    fp_per_class[cls_code] += 1
                elif is_gt and not is_pred:
                    fn_per_class[cls_code] += 1
                else:
                    tn_per_class[cls_code] += 1

        per_class_summary: dict[str, ClassMetricSummary] = {}
        valid_macro_precisions: list[float] = []
        valid_macro_recalls: list[float] = []
        valid_macro_f1s: list[float] = []

        total_tp_sum = 0
        total_fp_sum = 0
        total_fn_sum = 0

        for cls_code in vocab:
            tp = tp_per_class[cls_code]
            fp = fp_per_class[cls_code]
            fn = fn_per_class[cls_code]
            tn = tn_per_class[cls_code]
            supp = gt_pos_per_class[cls_code]

            total_tp_sum += tp
            total_fp_sum += fp
            total_fn_sum += fn

            p_c = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r_c = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_c = (2.0 * p_c * r_c) / (p_c + r_c) if (p_c + r_c) > 0 else 0.0

            status = (
                MetricAvailability.AVAILABLE
                if supp >= self.min_support_threshold
                else MetricAvailability.INSUFFICIENT_SUPPORT
            )

            per_class_summary[cls_code] = ClassMetricSummary(
                class_code=cls_code,
                precision=p_c,
                recall=r_c,
                f1=f1_c,
                support=supp,
                negative_support=total_frames - supp,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                true_negatives=tn,
                status=status,
                note=None if status == MetricAvailability.AVAILABLE else "insufficient sample size",
            )

            # Accumulate macro metrics for classes present in ground truth or predictions
            if supp > 0 or (tp + fp) > 0:
                valid_macro_precisions.append(p_c)
                valid_macro_recalls.append(r_c)
                valid_macro_f1s.append(f1_c)

        macro_p = (
            sum(valid_macro_precisions) / len(valid_macro_precisions)
            if valid_macro_precisions
            else 0.0
        )
        macro_r = (
            sum(valid_macro_recalls) / len(valid_macro_recalls)
            if valid_macro_recalls
            else 0.0
        )
        macro_f1 = (
            sum(valid_macro_f1s) / len(valid_macro_f1s)
            if valid_macro_f1s
            else 0.0
        )

        micro_p = (
            total_tp_sum / (total_tp_sum + total_fp_sum)
            if (total_tp_sum + total_fp_sum) > 0
            else 0.0
        )
        micro_r = (
            total_tp_sum / (total_tp_sum + total_fn_sum)
            if (total_tp_sum + total_fn_sum) > 0
            else 0.0
        )
        micro_f1 = (
            (2.0 * micro_p * micro_r) / (micro_p + micro_r)
            if (micro_p + micro_r) > 0
            else 0.0
        )

        return ClassificationMetricsReport(
            status=MetricAvailability.AVAILABLE,
            total_evaluated_frames=total_frames,
            macro_precision=macro_p,
            macro_recall=macro_r,
            macro_f1=macro_f1,
            micro_precision=micro_p,
            micro_recall=micro_r,
            micro_f1=micro_f1,
            exact_match_ratio=exact_matches / total_frames,
            per_class_metrics=per_class_summary,
        )

    def evaluate_calibration(
        self,
        paired_frames: Sequence[tuple[GroundTruthFrame, list[FusedInspectionObservation]]],
        num_bins: int = 10,
    ) -> CalibrationReport:
        """Assess confidence calibration and Expected Calibration Error (ECE)."""
        confidences: list[float] = []
        outcomes: list[int] = []

        for gt_frame, obs_list in paired_frames:
            gt_classes = set(gt_frame.presence.keys())
            for obs in obs_list:
                confidences.append(obs.confidence)
                is_correct = 1 if (obs.class_code in gt_classes and gt_frame.presence.get(obs.class_code, False)) else 0
                outcomes.append(is_correct)

        sample_count = len(confidences)
        if sample_count < 20:
            return CalibrationReport(
                status=MetricAvailability.INSUFFICIENT_SUPPORT,
                sample_count=sample_count,
                reason_if_unavailable="insufficient sample size for calibration indicator",
            )

        bins: list[CalibrationBin] = []
        bin_width = 1.0 / num_bins
        total_ece = 0.0

        for i in range(num_bins):
            lower = i * bin_width
            upper = (i + 1) * bin_width

            bin_confs: list[float] = []
            bin_outs: list[int] = []

            for conf, out in zip(confidences, outcomes):
                if lower <= conf < upper or (i == num_bins - 1 and conf == 1.0):
                    bin_confs.append(conf)
                    bin_outs.append(out)

            b_count = len(bin_confs)
            if b_count > 0:
                avg_conf = sum(bin_confs) / b_count
                emp_acc = sum(bin_outs) / b_count
                bins.append(
                    CalibrationBin(
                        bin_lower=lower,
                        bin_upper=upper,
                        sample_count=b_count,
                        avg_confidence=avg_conf,
                        empirical_accuracy=emp_acc,
                    )
                )
                total_ece += (b_count / sample_count) * abs(emp_acc - avg_conf)
            else:
                bins.append(
                    CalibrationBin(
                        bin_lower=lower,
                        bin_upper=upper,
                        sample_count=0,
                        avg_confidence=0.0,
                        empirical_accuracy=0.0,
                    )
                )

        return CalibrationReport(
            status=MetricAvailability.AVAILABLE,
            sample_count=sample_count,
            expected_calibration_error=total_ece,
            bins=bins,
        )

    def evaluate_localization(
        self,
        paired_frames: Sequence[tuple[GroundTruthFrame, float | None]],
    ) -> LocalizationMetricsReport:
        """Evaluate longitudinal position error against ground truth distance."""
        errors: list[float] = []

        for gt_frame, pred_dist in paired_frames:
            if gt_frame.true_distance_m is not None and pred_dist is not None:
                errors.append(abs(pred_dist - gt_frame.true_distance_m))

        if not errors:
            return LocalizationMetricsReport(
                status=MetricAvailability.UNAVAILABLE,
                sample_count=0,
                reason_if_unavailable="unavailable — no ground truth source for localization distance",
            )

        errors.sort()
        count = len(errors)
        mean_err = sum(errors) / count
        median_err = errors[count // 2]
        max_err = max(errors)

        p95_idx = math.ceil(0.95 * count) - 1
        p95_err = errors[max(0, min(p95_idx, count - 1))]

        return LocalizationMetricsReport(
            status=MetricAvailability.AVAILABLE,
            sample_count=count,
            mean_absolute_error_m=mean_err,
            median_absolute_error_m=median_err,
            max_absolute_error_m=max_err,
            p95_absolute_error_m=p95_err,
        )

    def evaluate_morphology(
        self,
        paired_frames: Sequence[tuple[GroundTruthFrame, float | None, float | None]],
    ) -> MorphologyMetricsReport:
        """Evaluate pipe diameter and deformation error against physical reference benchmarks."""
        diameter_errors: list[float] = []
        rel_errors: list[float] = []
        def_errors: list[float] = []

        for gt_frame, pred_diam, pred_def in paired_frames:
            if gt_frame.true_pipe_diameter_mm is not None and pred_diam is not None:
                d_err = abs(pred_diam - gt_frame.true_pipe_diameter_mm)
                diameter_errors.append(d_err)
                if gt_frame.true_pipe_diameter_mm > 0:
                    rel_errors.append((d_err / gt_frame.true_pipe_diameter_mm) * 100.0)

            if gt_frame.true_deformation_percent is not None and pred_def is not None:
                def_errors.append(abs(pred_def - gt_frame.true_deformation_percent))

        if not diameter_errors:
            return MorphologyMetricsReport(
                status=MetricAvailability.UNAVAILABLE,
                sample_count=0,
                calibration_status="UNCALIBRATED",
                reason_if_unavailable="unavailable — no ground truth source for physical morphology",
            )

        diameter_errors.sort()
        count = len(diameter_errors)

        return MorphologyMetricsReport(
            status=MetricAvailability.AVAILABLE,
            sample_count=count,
            calibration_status="CALIBRATED",
            mean_diameter_error_mm=sum(diameter_errors) / count,
            median_diameter_error_mm=diameter_errors[count // 2],
            mean_relative_diameter_error_percent=(
                sum(rel_errors) / len(rel_errors) if rel_errors else None
            ),
            mean_deformation_error_percent=(
                sum(def_errors) / len(def_errors) if def_errors else None
            ),
        )

    def evaluate_defect_locations(
        self,
        paired_frames: Sequence[tuple[GroundTruthFrame, list[FusedInspectionObservation]]],
    ) -> DefectLocationMetricsReport:
        """Evaluate spatial matching error for longitudinal defect positions."""
        spatial_errors: list[float] = []
        matched_count = 0
        unmatched_pred_count = 0
        unmatched_gt_count = 0
        has_gt_distance = False

        for gt_frame, obs_list in paired_frames:
            if gt_frame.true_distance_m is None:
                continue

            has_gt_distance = True
            gt_defects = list(gt_frame.defects)
            matched_gt: set[int] = set()

            for obs in obs_list:
                pred_dist = obs.distance_m
                if pred_dist is None:
                    unmatched_pred_count += 1
                    continue

                best_dist_err = float("inf")
                best_gt_idx = -1

                for idx, g_def in enumerate(gt_defects):
                    if idx in matched_gt:
                        continue
                    if g_def.class_code == obs.class_code:
                        dist_err = abs(pred_dist - gt_frame.true_distance_m)
                        if dist_err <= self.spatial_tolerance_m and dist_err < best_dist_err:
                            best_dist_err = dist_err
                            best_gt_idx = idx

                if best_gt_idx >= 0:
                    matched_count += 1
                    matched_gt.add(best_gt_idx)
                    spatial_errors.append(best_dist_err)
                else:
                    unmatched_pred_count += 1

            unmatched_gt_count += len(gt_defects) - len(matched_gt)

        if not has_gt_distance or (matched_count == 0 and unmatched_pred_count == 0 and unmatched_gt_count == 0):
            return DefectLocationMetricsReport(
                status=MetricAvailability.UNAVAILABLE,
                matched_defects_count=0,
                unmatched_predicted_count=0,
                unmatched_ground_truth_count=0,
                distance_tolerance_m=self.spatial_tolerance_m,
                reason_if_unavailable="unavailable — no ground truth defect location data",
            )

        mean_err = sum(spatial_errors) / len(spatial_errors) if spatial_errors else None
        max_err = max(spatial_errors) if spatial_errors else None

        return DefectLocationMetricsReport(
            status=MetricAvailability.AVAILABLE,
            matched_defects_count=matched_count,
            unmatched_predicted_count=unmatched_pred_count,
            unmatched_ground_truth_count=unmatched_gt_count,
            mean_spatial_error_m=mean_err,
            max_spatial_error_m=max_err,
            distance_tolerance_m=self.spatial_tolerance_m,
        )

    def evaluate_mission(
        self,
        ground_truth_mission: GroundTruthMission,
        ingestion_results: list[SingleIngestionResult],
        model_name: str = "PipeVision-InspectionPipeline",
        model_version: str = "v1.0",
    ) -> MissionEvaluationReport:
        """Evaluate an entire inspection mission and compile a reproducible MissionEvaluationReport."""
        # Index ingestion results by frame_id and filename stem
        results_by_id: dict[str, SingleIngestionResult] = {}
        for res in ingestion_results:
            results_by_id[res.frame_id] = res
            if res.frame_path:
                results_by_id[Path(res.frame_path).stem] = res

        paired_detection_cls: list[tuple[GroundTruthFrame, list[FusedInspectionObservation]]] = []
        paired_loc: list[tuple[GroundTruthFrame, float | None]] = []
        paired_morph: list[tuple[GroundTruthFrame, float | None, float | None]] = []

        total_frames = len(ground_truth_mission.frames)
        analyzed_frames = 0
        failed_frames = 0

        error_counts: dict[str, int] = defaultdict(int)

        for gt_frame in ground_truth_mission.frames:
            ingest_res: SingleIngestionResult | None = results_by_id.get(gt_frame.frame_id)
            if ingest_res is None and gt_frame.filename:
                ingest_res = results_by_id.get(Path(gt_frame.filename).stem)

            if ingest_res is None:
                failed_frames += 1
                error_counts[ErrorTaxonomy.INFERENCE_FAILURE.value] += 1
                continue

            analyzed_frames += 1
            obs_list = ingest_res.observations
            paired_detection_cls.append((gt_frame, obs_list))

            pred_dist = ingest_res.distance_m
            paired_loc.append((gt_frame, pred_dist))
            paired_morph.append((gt_frame, None, None))

            # Taxonomy accounting per observation
            gt_classes = set(gt_frame.presence.keys())
            for obs in obs_list:
                if obs.class_code in gt_classes and gt_frame.presence.get(obs.class_code, False):
                    error_counts[ErrorTaxonomy.TRUE_POSITIVE.value] += 1
                else:
                    error_counts[ErrorTaxonomy.FALSE_POSITIVE.value] += 1

            for cls_code, is_present in gt_frame.presence.items():
                if is_present and cls_code not in {obs.class_code for obs in obs_list}:
                    error_counts[ErrorTaxonomy.FALSE_NEGATIVE.value] += 1

        det_report = self.evaluate_detection(paired_detection_cls)
        cls_report = self.evaluate_classification(paired_detection_cls)
        cal_report = self.evaluate_calibration(paired_detection_cls)
        loc_report = self.evaluate_localization(paired_loc)
        morph_report = self.evaluate_morphology(paired_morph)
        def_loc_report = self.evaluate_defect_locations(paired_detection_cls)

        now_iso = datetime.now(timezone.utc).isoformat()

        return MissionEvaluationReport(
            evaluation_version="phase16-v1",
            dataset_source=ground_truth_mission.source,
            model_name=model_name,
            model_version=model_version,
            eval_timestamp_iso=now_iso,
            total_frames=total_frames,
            analyzed_frames=analyzed_frames,
            failed_frames=failed_frames,
            detection=det_report,
            classification=cls_report,
            calibration=cal_report,
            localization=loc_report,
            morphology=morph_report,
            defect_location=def_loc_report,
            error_taxonomy_counts=dict(error_counts),
            random_seed=self.random_seed,
        )
