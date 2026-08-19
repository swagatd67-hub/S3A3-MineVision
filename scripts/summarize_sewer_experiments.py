from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.video.sewer_dataset import DEFECT_CLASSES


EXPERIMENTS_DIR = Path("experiments/sewer")
SUMMARY_CSV_PATH = EXPERIMENTS_DIR / "summary.csv"


def build_summary() -> tuple[list[dict[str, Any]], str]:
    if not EXPERIMENTS_DIR.exists():
        return [], "No experiments directory found."

    exp_dirs = [d for d in EXPERIMENTS_DIR.iterdir() if d.is_dir()]
    rows: list[dict[str, Any]] = []

    for d in exp_dirs:
        config_p = d / "config.json"
        metrics_p = d / "metrics.json"

        if not config_p.exists():
            continue

        try:
            config = json.loads(config_p.read_text(encoding="utf-8"))
        except Exception:
            continue

        metrics = {}
        if metrics_p.exists():
            try:
                metrics = json.loads(metrics_p.read_text(encoding="utf-8"))
            except Exception:
                pass

        status = config.get("status", "COMPLETED")
        if status == "FAILED":
            row = {
                "experiment_id": d.name,
                "macro_f1_global": 0.0,
                "macro_f1_tuned": 0.0,
                "macro_recall_global": 0.0,
                "macro_recall_tuned": 0.0,
                "weighted_f1": 0.0,
                "weighted_recall": 0.0,
                "best_epoch": 0,
                "val_loss": 999.0,
                "training_time": config.get("training_time_seconds", 0.0),
                "batch_size": config.get("actual_batch_size", config.get("batch_size", 8)),
                "learning_rate": config.get("learning_rate", 0.0),
                "weight_decay": config.get("weight_decay", 0.0),
                "class_weight_mode": config.get("class_weight_mode", "none"),
                "class_weight_cap": config.get("class_weight_cap", None),
                "threshold_mode": config.get("threshold_mode", "global_0.5"),
                "config_path": str(config_p),
                "checkpoint_path": str(d / "best.pt"),
                "status": "FAILED",
                "_config": config,
                "_metrics": metrics,
            }
            rows.append(row)
            continue

        gl_metrics = metrics.get("global_threshold_0.5", {})
        tu_metrics = metrics.get("validation_derived_tuned_thresholds", {})

        row = {
            "experiment_id": d.name,
            "macro_f1_global": gl_metrics.get("macro_f1", 0.0),
            "macro_f1_tuned": tu_metrics.get("macro_f1", 0.0),
            "macro_recall_global": gl_metrics.get("macro_recall", 0.0),
            "macro_recall_tuned": tu_metrics.get("macro_recall", 0.0),
            "weighted_f1": gl_metrics.get("weighted_f1", 0.0),
            "weighted_recall": gl_metrics.get("weighted_recall", 0.0),
            "best_epoch": config.get("best_epoch", 0),
            "val_loss": metrics.get("val_loss", config.get("best_val_loss", 999.0)),
            "training_time": config.get("training_time_seconds", 0.0),
            "batch_size": config.get("actual_batch_size", config.get("batch_size", 8)),
            "learning_rate": config.get("learning_rate", 0.0),
            "weight_decay": config.get("weight_decay", 0.0),
            "class_weight_mode": config.get("class_weight_mode", "none"),
            "class_weight_cap": config.get("class_weight_cap", None),
            "threshold_mode": config.get("threshold_mode", "global_0.5"),
            "config_path": str(config_p),
            "checkpoint_path": str(d / "best.pt"),
            "status": "COMPLETED",
            "_config": config,
            "_metrics": metrics,
        }
        rows.append(row)

    # Sort rows by:
    # 1. macro_f1_tuned descending
    # 2. macro_f1_global descending
    # 3. macro_recall_tuned descending
    rows.sort(
        key=lambda r: (
            r["macro_f1_tuned"],
            r["macro_f1_global"],
            r["macro_recall_tuned"],
        ),
        reverse=True,
    )

    # Write summary.csv
    fieldnames = [
        "experiment_id",
        "macro_f1_global",
        "macro_f1_tuned",
        "macro_recall_global",
        "macro_recall_tuned",
        "weighted_f1",
        "weighted_recall",
        "best_epoch",
        "val_loss",
        "training_time",
        "batch_size",
        "learning_rate",
        "weight_decay",
        "class_weight_mode",
        "class_weight_cap",
        "threshold_mode",
        "config_path",
        "checkpoint_path",
    ]

    with SUMMARY_CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            clean_r = {k: v for k, v in r.items() if k in fieldnames}
            writer.writerow(clean_r)

    # Build report text
    report_lines = []
    report_lines.append("========================================")
    report_lines.append("PIPEVISION SEWER-ML EXPERIMENT SUMMARY")
    report_lines.append("========================================")
    report_lines.append("")

    if not rows:
        report_lines.append("No experiments found.")
        return rows, "\n".join(report_lines)

    best_exp = rows[0]
    best_cfg = best_exp["_config"]

    report_lines.append("BEST EXPERIMENT")
    report_lines.append(f"ID:                       {best_exp['experiment_id']}")
    report_lines.append(
        f"Configuration:            backbone={best_cfg.get('backbone', 'ResNet18')}, "
        f"pretrained={best_cfg.get('pretrained', True)}, "
        f"lr={best_exp['learning_rate']}, "
        f"wd={best_exp['weight_decay']}, "
        f"batch_size={best_exp['batch_size']}, "
        f"class_weight_mode={best_exp['class_weight_mode']}, "
        f"class_weight_cap={best_exp['class_weight_cap']}, "
        f"augmentation={best_cfg.get('augmentation_setting', 'baseline')}"
    )
    report_lines.append(f"Macro F1 (global 0.5):    {best_exp['macro_f1_global']:.4f}")
    report_lines.append(f"Macro F1 (tuned):         {best_exp['macro_f1_tuned']:.4f} (validation-derived)")
    report_lines.append(f"Macro Recall (global 0.5): {best_exp['macro_recall_global']:.4f}")
    report_lines.append(f"Macro Recall (tuned):      {best_exp['macro_recall_tuned']:.4f} (validation-derived)")
    report_lines.append(f"Weighted F1:               {best_exp['weighted_f1']:.4f}")
    report_lines.append(f"Best epoch:                {best_exp['best_epoch']}")
    report_lines.append(f"Validation loss:           {best_exp['val_loss']:.5f}")
    report_lines.append(f"Checkpoint:                {best_exp['checkpoint_path']}")
    report_lines.append("")

    report_lines.append("TOP 5 EXPERIMENTS")
    for i, r in enumerate(rows[:5], 1):
        report_lines.append(
            f"{i}. {r['experiment_id']:<6} | "
            f"Global F1: {r['macro_f1_global']:.4f} | "
            f"Tuned F1: {r['macro_f1_tuned']:.4f} | "
            f"Global Rec: {r['macro_recall_global']:.4f} | "
            f"Tuned Rec: {r['macro_recall_tuned']:.4f} | "
            f"Val Loss: {r['val_loss']:.4f}"
        )
    report_lines.append("")

    # Identify Weak Classes in Best Experiment
    report_lines.append("WEAK CLASSES")
    report_lines.append("(Evaluated on Best Experiment validation set)")

    best_metrics = best_exp["_metrics"]
    tu_pc = best_metrics.get("validation_derived_tuned_thresholds", {}).get("per_class", {})
    gl_pc = best_metrics.get("global_threshold_0.5", {}).get("per_class", {})

    weak_classes_data: list[tuple[str, int, float, float, float, int, int]] = []
    for cls_name in DEFECT_CLASSES:
        t_info = tu_pc.get(cls_name, {})
        g_info = gl_pc.get(cls_name, {})
        support = t_info.get("support", g_info.get("support", 0))
        prec = t_info.get("precision", g_info.get("precision", 0.0))
        rec = t_info.get("recall", g_info.get("recall", 0.0))
        f1 = t_info.get("f1", g_info.get("f1", 0.0))
        fp = t_info.get("false_positives", 0)
        fn = t_info.get("false_negatives", 0)

        # Flag as weak if F1 < 0.50 or recall < 0.50 or support < 5
        if f1 < 0.50 or rec < 0.50 or support < 5:
            weak_classes_data.append((cls_name, support, prec, rec, f1, fp, fn))

    if weak_classes_data:
        report_lines.append(f"{'CLASS':<6}{'SUPPORT':>8}{'PRECISION':>12}{'RECALL':>10}{'F1':>10}{'FP':>8}{'FN':>8}")
        report_lines.append("-" * 65)
        for cls_name, supp, prec, rec, f1, fp, fn in weak_classes_data:
            report_lines.append(f"{cls_name:<6}{supp:>8}{prec:>12.3f}{rec:>10.3f}{f1:>10.3f}{fp:>8}{fn:>8}")
    else:
        report_lines.append("No weak classes detected under threshold criteria.")

    report_lines.append("")
    report_lines.append("RECOMMENDED NEXT ACTION")
    # Action selection logic based on evidence:
    # Check if low support classes dominate weak classes
    low_supp_count = sum(1 for _, supp, _, _, _, _, _ in weak_classes_data if supp < 5)
    if low_supp_count > 0:
        recommendation = "collect more data for specific classes"
        reason = f"{low_supp_count} defect classes have very low validation support (<5 samples) leading to high variance and 0 recall/precision."
    elif best_exp['macro_f1_tuned'] - best_exp['macro_f1_global'] > 0.08:
        recommendation = "improve calibration"
        reason = "Validation threshold tuning yields a significant boost over fixed 0.5 threshold."
    else:
        recommendation = "keep current best model"
        reason = "Current best experiment delivers balanced Macro F1 and Recall on the development split."

    report_lines.append(f"RECOMMENDATION: {recommendation}")
    report_lines.append(f"REASON:         {reason}")
    report_lines.append("")

    return rows, "\n".join(report_lines)


def main() -> None:
    _, report = build_summary()
    print(report)


if __name__ == "__main__":
    main()
