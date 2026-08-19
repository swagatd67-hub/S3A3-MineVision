from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
from sklearn.metrics import f1_score, precision_score, recall_score

from backend.app.services.video.sewer_dataset import DEFECT_CLASSES


THRESHOLD_SWEEP = [
    0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
    0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90
]


def evaluate_predictions(
    targets: np.ndarray,
    probabilities: np.ndarray,
    filenames: list[str] | None = None,
    val_loss: float = 0.0,
) -> tuple[dict[str, Any], dict[str, float], dict[str, Any]]:
    """
    Computes global threshold (0.5) and validation-derived tuned threshold metrics.
    Returns (metrics_dict, thresholds_dict, predictions_dict).
    """
    num_samples, num_classes = targets.shape
    assert num_classes == len(DEFECT_CLASSES)

    # 1. Global Threshold 0.5 Metrics
    y_pred_global = (probabilities >= 0.5).astype(int)

    macro_f1_global = float(f1_score(targets, y_pred_global, average="macro", zero_division=0))
    macro_recall_global = float(recall_score(targets, y_pred_global, average="macro", zero_division=0))
    weighted_f1_global = float(f1_score(targets, y_pred_global, average="weighted", zero_division=0))
    weighted_recall_global = float(recall_score(targets, y_pred_global, average="weighted", zero_division=0))

    per_class_global: dict[str, dict[str, Any]] = {}
    for idx, cls_name in enumerate(DEFECT_CLASSES):
        y_t = targets[:, idx]
        y_p = y_pred_global[:, idx]
        support = int(np.sum(y_t))
        prec = float(precision_score(y_t, y_p, zero_division=0))
        rec = float(recall_score(y_t, y_p, zero_division=0))
        f1 = float(f1_score(y_t, y_p, zero_division=0))
        per_class_global[cls_name] = {
            "support": support,
            "precision": prec,
            "recall": rec,
            "f1": f1,
        }

    # 2. Validation-Derived Tuned Thresholds
    best_thresholds: dict[str, float] = {}
    y_pred_tuned = np.zeros_like(y_pred_global)

    for idx, cls_name in enumerate(DEFECT_CLASSES):
        y_t = targets[:, idx]
        p_c = probabilities[:, idx]

        best_t = 0.5
        best_cls_f1 = -1.0

        for t in THRESHOLD_SWEEP:
            pred_t = (p_c >= t).astype(int)
            f1_t = float(f1_score(y_t, pred_t, zero_division=0))
            # Tie breaker: choose threshold closest to 0.5 if F1 is equal
            if f1_t > best_cls_f1 or (abs(f1_t - best_cls_f1) < 1e-7 and abs(t - 0.5) < abs(best_t - 0.5)):
                best_cls_f1 = f1_t
                best_t = t

        best_thresholds[cls_name] = round(best_t, 2)
        y_pred_tuned[:, idx] = (p_c >= best_t).astype(int)

    macro_f1_tuned = float(f1_score(targets, y_pred_tuned, average="macro", zero_division=0))
    macro_recall_tuned = float(recall_score(targets, y_pred_tuned, average="macro", zero_division=0))
    weighted_f1_tuned = float(f1_score(targets, y_pred_tuned, average="weighted", zero_division=0))
    weighted_recall_tuned = float(recall_score(targets, y_pred_tuned, average="weighted", zero_division=0))

    per_class_tuned: dict[str, dict[str, Any]] = {}
    for idx, cls_name in enumerate(DEFECT_CLASSES):
        y_t = targets[:, idx]
        y_p = y_pred_tuned[:, idx]
        support = int(np.sum(y_t))
        prec = float(precision_score(y_t, y_p, zero_division=0))
        rec = float(recall_score(y_t, y_p, zero_division=0))
        f1 = float(f1_score(y_t, y_p, zero_division=0))
        fp = int(np.sum((y_t == 0) & (y_p == 1)))
        fn = int(np.sum((y_t == 1) & (y_p == 0)))
        per_class_tuned[cls_name] = {
            "support": support,
            "threshold": best_thresholds[cls_name],
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "false_positives": fp,
            "false_negatives": fn,
        }

    metrics = {
        "val_loss": float(val_loss),
        "global_threshold_0.5": {
            "macro_f1": macro_f1_global,
            "macro_recall": macro_recall_global,
            "weighted_f1": weighted_f1_global,
            "weighted_recall": weighted_recall_global,
            "per_class": per_class_global,
        },
        "validation_derived_tuned_thresholds": {
            "macro_f1": macro_f1_tuned,
            "macro_recall": macro_recall_tuned,
            "weighted_f1": weighted_f1_tuned,
            "weighted_recall": weighted_recall_tuned,
            "per_class": per_class_tuned,
        },
    }

    predictions = {
        "filenames": filenames or [],
        "targets": targets.tolist(),
        "probabilities": probabilities.tolist(),
    }

    return metrics, best_thresholds, predictions


def save_experiment_evaluation(
    exp_dir: Path,
    targets: np.ndarray,
    probabilities: np.ndarray,
    filenames: list[str] | None = None,
    val_loss: float = 0.0,
) -> dict[str, Any]:
    exp_dir.mkdir(parents=True, exist_ok=True)

    metrics, thresholds, predictions = evaluate_predictions(
        targets, probabilities, filenames=filenames, val_loss=val_loss
    )

    (exp_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (exp_dir / "thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    (exp_dir / "predictions.json").write_text(json.dumps(predictions, indent=2), encoding="utf-8")

    # Generate classification_report.txt
    lines = []
    lines.append(f"EXPERIMENT EVALUATION REPORT: {exp_dir.name}")
    lines.append("=" * 70)
    lines.append(f"Validation Loss: {val_loss:.5f}")
    lines.append("")
    lines.append("GLOBAL THRESHOLD (0.5) OVERALL METRICS:")
    lines.append(f"  Macro F1:       {metrics['global_threshold_0.5']['macro_f1']:.4f}")
    lines.append(f"  Macro Recall:   {metrics['global_threshold_0.5']['macro_recall']:.4f}")
    lines.append(f"  Weighted F1:    {metrics['global_threshold_0.5']['weighted_f1']:.4f}")
    lines.append(f"  Weighted Recall:{metrics['global_threshold_0.5']['weighted_recall']:.4f}")
    lines.append("")
    lines.append("VALIDATION-DERIVED TUNED THRESHOLD OVERALL METRICS:")
    lines.append(f"  Macro F1:       {metrics['validation_derived_tuned_thresholds']['macro_f1']:.4f}")
    lines.append(f"  Macro Recall:   {metrics['validation_derived_tuned_thresholds']['macro_recall']:.4f}")
    lines.append(f"  Weighted F1:    {metrics['validation_derived_tuned_thresholds']['weighted_f1']:.4f}")
    lines.append(f"  Weighted Recall:{metrics['validation_derived_tuned_thresholds']['weighted_recall']:.4f}")
    lines.append("")
    lines.append(f"{'CLASS':<6}{'SUPP':>6} | {'GL_PR':>7} {'GL_REC':>7} {'GL_F1':>7} | {'T_THRESH':>8} {'T_PR':>7} {'T_REC':>7} {'T_F1':>7}")
    lines.append("-" * 75)

    gl_pc = metrics['global_threshold_0.5']['per_class']
    tu_pc = metrics['validation_derived_tuned_thresholds']['per_class']

    for cls_name in DEFECT_CLASSES:
        g = gl_pc[cls_name]
        t = tu_pc[cls_name]
        lines.append(
            f"{cls_name:<6}{g['support']:>6} | "
            f"{g['precision']:>7.3f} {g['recall']:>7.3f} {g['f1']:>7.3f} | "
            f"{t['threshold']:>8.2f} {t['precision']:>7.3f} {t['recall']:>7.3f} {t['f1']:>7.3f}"
        )

    (exp_dir / "classification_report.txt").write_text("\n".join(lines), encoding="utf-8")
    return metrics
