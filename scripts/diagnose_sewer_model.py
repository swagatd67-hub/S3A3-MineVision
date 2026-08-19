#!/usr/bin/env python
"""
PipeVision E002 Diagnostic Analysis Script
===========================================

Performs a targeted diagnostic analysis of the current best Sewer-ML model
(E002) WITHOUT retraining.  Generates structured outputs explaining WHY
the model performs poorly on specific defect classes.

Output directory:  experiments/sewer/E002/diagnostics/
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch
from torch.amp import autocast
from torch.utils.data import DataLoader
from torchvision import transforms

from backend.app.services.video.sewer_dataset import (
    DEFECT_CLASSES,
    SewerMLDataset,
)
from backend.app.services.video.sewer_model import SewerDefectClassifier

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IMAGE_DIR = Path("approved-data/sewer-ml/images/train00_subset")
CSV_PATH = Path("approved-data/sewer-ml/extracted/SewerML_Train.csv")
VAL_SPLIT = Path("approved-data/sewer-ml/splits/val.csv")
CHECKPOINT = Path("experiments/sewer/E002/best.pt")
THRESHOLDS_PATH = Path("experiments/sewer/E002/thresholds.json")
DIAGNOSTICS_DIR = Path("experiments/sewer/E002/diagnostics")

WEAK_CLASSES = ["PH", "GR", "FO", "RO", "PB", "OS", "OP"]
GLOBAL_THRESHOLD = 0.5


# ===================================================================
# STEP 1 — LOAD MODEL
# ===================================================================
def load_model(device: torch.device) -> SewerDefectClassifier:
    """Load the E002 best checkpoint onto *device* in eval mode."""
    print("=" * 60)
    print("STEP 1: LOADING MODEL")
    print("=" * 60)

    assert CHECKPOINT.exists(), f"Checkpoint not found: {CHECKPOINT}"
    checkpoint = torch.load(CHECKPOINT, map_location=device, weights_only=False)

    model = SewerDefectClassifier(
        num_classes=len(DEFECT_CLASSES),
        pretrained=False,          # weights come from the checkpoint
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    print(f"  Loaded checkpoint from epoch {checkpoint.get('epoch', '?')}")
    print(f"  Device: {device}")
    if device.type == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  Classes: {len(DEFECT_CLASSES)}")
    return model


# ===================================================================
# STEP 2 — VERIFY VALIDATION MANIFEST
# ===================================================================
def load_and_verify_val_manifest() -> list[str]:
    """Load val.csv, verify integrity, return list of filenames."""
    print("\n" + "=" * 60)
    print("STEP 2: VERIFYING VALIDATION MANIFEST")
    print("=" * 60)

    assert VAL_SPLIT.exists(), f"Val split not found: {VAL_SPLIT}"

    with VAL_SPLIT.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    filenames = [r["Filename"] for r in rows]
    print(f"  Validation images listed: {len(filenames)}")

    # duplicates
    unique = set(filenames)
    assert len(unique) == len(filenames), \
        f"Duplicate filenames found: {len(filenames) - len(unique)}"
    print("  No duplicate filenames ✓")

    # images exist
    missing = [f for f in filenames if not (IMAGE_DIR / f).is_file()]
    assert len(missing) == 0, f"Missing images: {missing}"
    print("  All images exist on disk ✓")

    # load full label CSV to verify classes + binary
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        label_rows = {r["Filename"]: r for r in csv.DictReader(fh)}

    for fn in filenames:
        assert fn in label_rows, f"Filename {fn} missing from label CSV"
        for cls in DEFECT_CLASSES:
            assert cls in label_rows[fn], f"Class {cls} missing for {fn}"
            assert label_rows[fn][cls] in ("0", "1"), \
                f"Non-binary label for {fn}:{cls} = {label_rows[fn][cls]}"

    print(f"  All 17 classes present ✓")
    print(f"  All labels binary ✓")
    return filenames


# ===================================================================
# STEP 3 — GENERATE VALIDATION PREDICTIONS
# ===================================================================
def generate_predictions(
    model: SewerDefectClassifier,
    filenames: list[str],
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Run inference, return (y_true, y_prob, ordered_filenames)."""
    print("\n" + "=" * 60)
    print("STEP 3: GENERATING VALIDATION PREDICTIONS")
    print("=" * 60)

    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225),
        ),
    ])

    dataset = SewerMLDataset(
        image_dir=IMAGE_DIR,
        csv_path=CSV_PATH,
        filenames=filenames,
        image_size=224,
        training=False,
        transform=val_transform,
    )

    loader = DataLoader(
        dataset,
        batch_size=16,
        shuffle=False,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )

    all_targets: list[torch.Tensor] = []
    all_probs: list[torch.Tensor] = []
    all_fnames: list[str] = []

    with torch.no_grad():
        for images, targets, fnames in loader:
            images = images.to(device, non_blocking=True)
            logits = model(images)
            probs = torch.sigmoid(logits).cpu()
            all_targets.append(targets)
            all_probs.append(probs)
            all_fnames.extend(fnames)

    y_true = torch.cat(all_targets, dim=0).numpy()
    y_prob = torch.cat(all_probs, dim=0).numpy()

    print(f"  Predictions generated for {len(all_fnames)} images")
    print(f"  y_true shape: {y_true.shape}")
    print(f"  y_prob shape:  {y_prob.shape}")

    return y_true, y_prob, all_fnames


# ===================================================================
# STEP 4 — CLASS DIAGNOSTICS
# ===================================================================
def compute_class_diagnostics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    tuned_thresholds: dict[str, float] | None,
) -> list[dict[str, Any]]:
    """Per-class diagnostics using global threshold 0.5."""
    print("\n" + "=" * 60)
    print("STEP 4: COMPUTING CLASS DIAGNOSTICS")
    print("=" * 60)

    records: list[dict[str, Any]] = []

    for idx, cls in enumerate(DEFECT_CLASSES):
        t = y_true[:, idx]
        p = y_prob[:, idx]

        # counts
        pos_mask = t == 1
        neg_mask = t == 0
        n_pos = int(pos_mask.sum())
        n_neg = int(neg_mask.sum())

        pred_05 = (p >= GLOBAL_THRESHOLD).astype(int)
        tp = int(((pred_05 == 1) & (t == 1)).sum())
        fp = int(((pred_05 == 1) & (t == 0)).sum())
        fn = int(((pred_05 == 0) & (t == 1)).sum())
        tn = int(((pred_05 == 0) & (t == 0)).sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        f2 = (5 * precision * recall) / (4 * precision + recall) if (4 * precision + recall) > 0 else 0.0

        # probability statistics
        pos_probs = p[pos_mask] if n_pos > 0 else np.array([])
        neg_probs = p[neg_mask] if n_neg > 0 else np.array([])

        avg_pos = float(pos_probs.mean()) if len(pos_probs) > 0 else None
        avg_neg = float(neg_probs.mean()) if len(neg_probs) > 0 else None
        med_pos = float(np.median(pos_probs)) if len(pos_probs) > 0 else None
        med_neg = float(np.median(neg_probs)) if len(neg_probs) > 0 else None
        min_pos = float(pos_probs.min()) if len(pos_probs) > 0 else None
        max_pos = float(pos_probs.max()) if len(pos_probs) > 0 else None
        min_neg = float(neg_probs.min()) if len(neg_probs) > 0 else None
        max_neg = float(neg_probs.max()) if len(neg_probs) > 0 else None

        if avg_pos is not None and avg_neg is not None:
            prob_sep = avg_pos - avg_neg
        else:
            prob_sep = None

        threshold_tuned = tuned_thresholds.get(cls, GLOBAL_THRESHOLD) if tuned_thresholds else GLOBAL_THRESHOLD

        rec = {
            "class": cls,
            "support": n_pos,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "f2": round(f2, 6),
            "avg_pos_prob": round(avg_pos, 6) if avg_pos is not None else None,
            "avg_neg_prob": round(avg_neg, 6) if avg_neg is not None else None,
            "median_pos_prob": round(med_pos, 6) if med_pos is not None else None,
            "median_neg_prob": round(med_neg, 6) if med_neg is not None else None,
            "min_pos_prob": round(min_pos, 6) if min_pos is not None else None,
            "max_pos_prob": round(max_pos, 6) if max_pos is not None else None,
            "min_neg_prob": round(min_neg, 6) if min_neg is not None else None,
            "max_neg_prob": round(max_neg, 6) if max_neg is not None else None,
            "probability_separation": round(prob_sep, 6) if prob_sep is not None else None,
            "tuned_threshold": threshold_tuned,
        }
        records.append(rec)

        print(f"  {cls:3s} | support={n_pos:3d} | F1={f1:.4f} | prec={precision:.4f} | "
              f"rec={recall:.4f} | sep={prob_sep:.4f}" if prob_sep is not None else
              f"  {cls:3s} | support={n_pos:3d} | F1={f1:.4f} | prec={precision:.4f} | "
              f"rec={recall:.4f} | sep=N/A")

    return records


# ===================================================================
# STEP 5 — FAILURE CASES
# ===================================================================
def extract_failure_cases(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    filenames: list[str],
    tuned_thresholds: dict[str, float] | None,
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Extract FP/FN for weak classes at global threshold 0.5."""
    print("\n" + "=" * 60)
    print("STEP 5: EXTRACTING FAILURE CASES")
    print("=" * 60)

    false_positives: dict[str, list[dict]] = {}
    false_negatives: dict[str, list[dict]] = {}

    for cls in WEAK_CLASSES:
        idx = DEFECT_CLASSES.index(cls)
        t = y_true[:, idx]
        p = y_prob[:, idx]
        pred = (p >= GLOBAL_THRESHOLD).astype(int)
        threshold_tuned = tuned_thresholds.get(cls, GLOBAL_THRESHOLD) if tuned_thresholds else GLOBAL_THRESHOLD

        fps = []
        fns = []

        for i in range(len(filenames)):
            entry = {
                "filename": filenames[i],
                "true_label": int(t[i]),
                "predicted_probability": round(float(p[i]), 6),
                "threshold": GLOBAL_THRESHOLD,
                "tuned_threshold": threshold_tuned,
                "predicted_label": int(pred[i]),
            }
            if t[i] == 0 and pred[i] == 1:
                fps.append(entry)
            elif t[i] == 1 and pred[i] == 0:
                fns.append(entry)

        # sort FPs by probability descending, FNs by probability ascending
        fps.sort(key=lambda x: x["predicted_probability"], reverse=True)
        fns.sort(key=lambda x: x["predicted_probability"])

        false_positives[cls] = fps[:50]
        false_negatives[cls] = fns[:50]

        print(f"  {cls:3s} | FP={len(fps):3d} | FN={len(fns):3d}")

    return false_positives, false_negatives


# ===================================================================
# STEP 6 — DIAGNOSIS CLASSIFICATION
# ===================================================================
def classify_diagnosis(
    diagnostics: list[dict[str, Any]],
    tuned_thresholds: dict[str, float] | None,
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> list[dict[str, Any]]:
    """Classify the likely issue for each class based on evidence."""
    print("\n" + "=" * 60)
    print("STEP 6: CLASSIFYING DIAGNOSES")
    print("=" * 60)

    for rec in diagnostics:
        cls = rec["class"]
        idx = DEFECT_CLASSES.index(cls)
        support = rec["support"]
        f1 = rec["f1"]
        precision = rec["precision"]
        recall = rec["recall"]
        prob_sep = rec["probability_separation"]
        fp = rec["fp"]
        fn = rec["fn"]
        tn = rec["tn"]
        tp = rec["tp"]

        threshold_tuned = tuned_thresholds.get(cls, GLOBAL_THRESHOLD) if tuned_thresholds else GLOBAL_THRESHOLD

        # Compute tuned-threshold F1 for threshold comparison
        t = y_true[:, idx]
        p = y_prob[:, idx]
        pred_tuned = (p >= threshold_tuned).astype(int)
        tp_t = int(((pred_tuned == 1) & (t == 1)).sum())
        fp_t = int(((pred_tuned == 1) & (t == 0)).sum())
        fn_t = int(((pred_tuned == 0) & (t == 1)).sum())
        prec_t = tp_t / (tp_t + fp_t) if (tp_t + fp_t) > 0 else 0.0
        rec_t = tp_t / (tp_t + fn_t) if (tp_t + fn_t) > 0 else 0.0
        f1_tuned = 2 * prec_t * rec_t / (prec_t + rec_t) if (prec_t + rec_t) > 0 else 0.0

        rec["f1_tuned"] = round(f1_tuned, 6)
        rec["precision_tuned"] = round(prec_t, 6)
        rec["recall_tuned"] = round(rec_t, 6)

        diagnosis = "UNCERTAIN"
        reasoning = ""

        if support < 3:
            diagnosis = "INSUFFICIENT_VALIDATION_SUPPORT"
            reasoning = f"Only {support} positive sample(s) in validation set"
        elif support < 5:
            diagnosis = "DATA_LIMITED"
            reasoning = f"Only {support} positive samples — too few for reliable evaluation"
        elif prob_sep is not None and prob_sep < 0.10:
            diagnosis = "LOW_PROBABILITY_SEPARATION"
            reasoning = (f"Positive/negative probability distributions overlap heavily "
                         f"(separation={prob_sep:.4f})")
        elif f1 < 0.20 and f1_tuned > f1 + 0.15:
            diagnosis = "THRESHOLD_PROBLEM"
            reasoning = (f"Global F1={f1:.4f} but tuned F1={f1_tuned:.4f} "
                         f"(+{f1_tuned - f1:.4f}) — threshold tuning helps significantly")
        elif prob_sep is not None and prob_sep < 0.20 and recall < 0.30:
            diagnosis = "LOW_PROBABILITY_SEPARATION"
            reasoning = (f"Model gives low probabilities to positives "
                         f"(avg_pos={rec['avg_pos_prob']}, sep={prob_sep:.4f})")
        elif support > 0 and fn > 0.7 * support and recall < 0.20:
            diagnosis = "HIGH_FALSE_NEGATIVE_RATE"
            reasoning = (f"{fn}/{support} positives missed (recall={recall:.4f}), "
                         f"avg_pos_prob={rec['avg_pos_prob']}")
        elif fp > 0 and tn > 0 and fp / (fp + tn) > 0.15:
            diagnosis = "HIGH_FALSE_POSITIVE_RATE"
            reasoning = f"FPR = {fp}/{fp + tn} = {fp / (fp + tn):.4f}"
        elif f1 >= 0.50 and prob_sep is not None and prob_sep >= 0.20:
            diagnosis = "PROMISING"
            reasoning = f"Reasonable F1={f1:.4f}, separation={prob_sep:.4f}"
        elif f1 >= 0.40:
            diagnosis = "PROMISING"
            reasoning = f"Moderate F1={f1:.4f}"

        rec["diagnosis"] = diagnosis
        rec["reasoning"] = reasoning

        print(f"  {cls:3s} → {diagnosis} | {reasoning}")

    return diagnostics


# ===================================================================
# STEP 7 — FAILURE CASES CSV
# ===================================================================
def save_failure_cases_csv(
    false_positives: dict[str, list[dict]],
    false_negatives: dict[str, list[dict]],
) -> Path:
    """Save failure_cases.csv for visual inspection."""
    print("\n" + "=" * 60)
    print("STEP 7: SAVING FAILURE CASES CSV")
    print("=" * 60)

    out_path = DIAGNOSTICS_DIR / "failure_cases.csv"
    fieldnames = ["class", "filename", "true_label",
                  "predicted_probability", "threshold", "error_type"]

    rows: list[dict] = []

    for cls in WEAK_CLASSES:
        for entry in false_positives.get(cls, []):
            rows.append({
                "class": cls,
                "filename": entry["filename"],
                "true_label": entry["true_label"],
                "predicted_probability": entry["predicted_probability"],
                "threshold": GLOBAL_THRESHOLD,
                "error_type": "FALSE_POSITIVE",
            })
        for entry in false_negatives.get(cls, []):
            rows.append({
                "class": cls,
                "filename": entry["filename"],
                "true_label": entry["true_label"],
                "predicted_probability": entry["predicted_probability"],
                "threshold": GLOBAL_THRESHOLD,
                "error_type": "FALSE_NEGATIVE",
            })

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Saved {len(rows)} failure cases → {out_path}")
    return out_path


# ===================================================================
# STEP 8 — FINAL REPORT
# ===================================================================
def recommend_action(rec: dict[str, Any]) -> str:
    """Return exactly one recommended action for a weak class."""
    diag = rec["diagnosis"]
    prob_sep = rec.get("probability_separation")
    avg_pos = rec.get("avg_pos_prob")

    if diag == "INSUFFICIENT_VALIDATION_SUPPORT":
        return "COLLECT_MORE_DATA"
    elif diag == "DATA_LIMITED":
        return "COLLECT_MORE_DATA"
    elif diag == "THRESHOLD_PROBLEM":
        return "TUNE_THRESHOLD"
    elif diag == "LOW_PROBABILITY_SEPARATION":
        if avg_pos is not None and avg_pos < 0.15:
            return "INVESTIGATE_VISUAL_CONFUSION"
        return "INSPECT_LABELS"
    elif diag == "HIGH_FALSE_NEGATIVE_RATE":
        if avg_pos is not None and avg_pos < 0.20:
            return "INVESTIGATE_VISUAL_CONFUSION"
        return "CHANGE_AUGMENTATION"
    elif diag == "HIGH_FALSE_POSITIVE_RATE":
        return "INSPECT_LABELS"
    elif diag == "PROMISING":
        return "NO_ACTION_YET"
    else:
        return "INSPECT_LABELS"


def print_final_report(diagnostics: list[dict[str, Any]]) -> str:
    """Print and return final diagnostic report."""
    lines: list[str] = []

    def out(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    out()
    out("=" * 72)
    out("PIPEVISION E002 CLASS DIAGNOSTICS")
    out("=" * 72)
    out()
    header = (f"{'CLASS':>5s} {'SUPPORT':>7s} {'PREC':>7s} {'RECALL':>7s} "
              f"{'F1':>7s} {'F2':>7s} {'AVG_POS':>8s} {'AVG_NEG':>8s} "
              f"{'PROB_SEP':>9s} {'THRESH':>7s} {'DIAGNOSIS'}")
    out(header)
    out("-" * len(header))

    for rec in diagnostics:
        avg_pos = f"{rec['avg_pos_prob']:.4f}" if rec['avg_pos_prob'] is not None else "N/A"
        avg_neg = f"{rec['avg_neg_prob']:.4f}" if rec['avg_neg_prob'] is not None else "N/A"
        sep = f"{rec['probability_separation']:.4f}" if rec['probability_separation'] is not None else "N/A"

        out(f"{rec['class']:>5s} {rec['support']:>7d} {rec['precision']:>7.4f} "
            f"{rec['recall']:>7.4f} {rec['f1']:>7.4f} {rec['f2']:>7.4f} "
            f"{avg_pos:>8s} {avg_neg:>8s} {sep:>9s} "
            f"{rec['tuned_threshold']:>7.2f} {rec['diagnosis']}")

    out()
    out("=" * 72)
    out("TARGETED WEAK-CLASS ANALYSIS")
    out("=" * 72)
    out()

    for cls in WEAK_CLASSES:
        rec = next(r for r in diagnostics if r["class"] == cls)
        out(f"--- {cls} ---")
        out(f"  Support:                {rec['support']}")
        out(f"  F1 (global 0.5):        {rec['f1']:.4f}")
        out(f"  F1 (tuned threshold):   {rec.get('f1_tuned', 'N/A')}")
        out(f"  Precision:              {rec['precision']:.4f}")
        out(f"  Recall:                 {rec['recall']:.4f}")
        out(f"  FP:                     {rec['fp']}")
        out(f"  FN:                     {rec['fn']}")
        sep_str = f"{rec['probability_separation']:.4f}" if rec['probability_separation'] is not None else "N/A"
        out(f"  Probability Separation: {sep_str}")
        out(f"  Avg Positive Prob:      {rec['avg_pos_prob']}")
        out(f"  Avg Negative Prob:      {rec['avg_neg_prob']}")
        out(f"  Min/Max Pos Prob:       {rec['min_pos_prob']} / {rec['max_pos_prob']}")
        out(f"  Tuned Threshold:        {rec['tuned_threshold']}")
        out(f"  Diagnosis:              {rec['diagnosis']}")
        out(f"  Reasoning:              {rec['reasoning']}")
        out()

    # Recommended actions
    out("=" * 72)
    out("RECOMMENDED NEXT ACTION")
    out("=" * 72)
    out()

    for cls in WEAK_CLASSES:
        rec = next(r for r in diagnostics if r["class"] == cls)
        action = recommend_action(rec)
        rec["recommended_action"] = action
        out(f"  {cls:3s} → {action}")

    # Final summary table
    out()
    out("=" * 72)
    out("FINAL SUMMARY TABLE")
    out("=" * 72)
    out()

    hdr2 = f"{'CLASS':>5s} | {'SUPPORT':>7s} | {'F1':>7s} | {'PREC':>7s} | {'RECALL':>7s} | {'FP':>4s} | {'FN':>4s} | DIAGNOSIS"
    out(hdr2)
    out("-" * len(hdr2))
    for rec in diagnostics:
        out(f"{rec['class']:>5s} | {rec['support']:>7d} | {rec['f1']:>7.4f} | "
            f"{rec['precision']:>7.4f} | {rec['recall']:>7.4f} | "
            f"{rec['fp']:>4d} | {rec['fn']:>4d} | {rec['diagnosis']}")

    # Priority groups
    out()
    data_priority = [r["class"] for r in diagnostics
                     if r["diagnosis"] in ("DATA_LIMITED", "INSUFFICIENT_VALIDATION_SUPPORT")]
    investigate = [r["class"] for r in diagnostics
                   if r["diagnosis"] in ("LOW_PROBABILITY_SEPARATION",
                                          "HIGH_FALSE_NEGATIVE_RATE",
                                          "HIGH_FALSE_POSITIVE_RATE")]
    threshold_sensitive = [r["class"] for r in diagnostics
                           if r["diagnosis"] == "THRESHOLD_PROBLEM"]

    out(f"TOP PRIORITY DATA CLASSES:          {', '.join(data_priority) if data_priority else 'None'}")
    out(f"TOP PRIORITY INVESTIGATION CLASSES: {', '.join(investigate) if investigate else 'None'}")
    out(f"THRESHOLD-SENSITIVE CLASSES:         {', '.join(threshold_sensitive) if threshold_sensitive else 'None'}")
    out()

    return "\n".join(lines)


# ===================================================================
# MAIN
# ===================================================================
def main() -> None:
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Step 1
    model = load_model(device)

    # Step 2
    filenames = load_and_verify_val_manifest()

    # Step 3
    y_true, y_prob, ordered_fnames = generate_predictions(model, filenames, device)

    # Load tuned thresholds if available
    tuned_thresholds: dict[str, float] | None = None
    if THRESHOLDS_PATH.exists():
        tuned_thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
        print(f"\n  Loaded tuned thresholds from {THRESHOLDS_PATH}")

    # Step 4
    diagnostics = compute_class_diagnostics(y_true, y_prob, tuned_thresholds)

    # Step 5
    false_positives, false_negatives = extract_failure_cases(
        y_true, y_prob, ordered_fnames, tuned_thresholds
    )

    # Step 6
    diagnostics = classify_diagnosis(diagnostics, tuned_thresholds, y_true, y_prob)

    # --- Save outputs ---
    # class_diagnostics.csv
    csv_path = DIAGNOSTICS_DIR / "class_diagnostics.csv"
    fieldnames = list(diagnostics[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(diagnostics)
    print(f"\n  Saved → {csv_path}")

    # probability_statistics.csv
    prob_csv = DIAGNOSTICS_DIR / "probability_statistics.csv"
    prob_fields = ["class", "support", "avg_pos_prob", "avg_neg_prob",
                   "median_pos_prob", "median_neg_prob",
                   "min_pos_prob", "max_pos_prob",
                   "min_neg_prob", "max_neg_prob",
                   "probability_separation"]
    with prob_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=prob_fields)
        writer.writeheader()
        for rec in diagnostics:
            writer.writerow({k: rec[k] for k in prob_fields})
    print(f"  Saved → {prob_csv}")

    # false_positives.json
    fp_path = DIAGNOSTICS_DIR / "false_positives.json"
    fp_path.write_text(json.dumps(false_positives, indent=2), encoding="utf-8")
    print(f"  Saved → {fp_path}")

    # false_negatives.json
    fn_path = DIAGNOSTICS_DIR / "false_negatives.json"
    fn_path.write_text(json.dumps(false_negatives, indent=2), encoding="utf-8")
    print(f"  Saved → {fn_path}")

    # Step 7
    save_failure_cases_csv(false_positives, false_negatives)

    # Step 8 — Final report
    report = print_final_report(diagnostics)

    # summary.json
    summary: dict[str, Any] = {
        "model_checkpoint": str(CHECKPOINT),
        "validation_images": len(ordered_fnames),
        "num_classes": len(DEFECT_CLASSES),
        "global_threshold": GLOBAL_THRESHOLD,
        "tuned_thresholds_available": tuned_thresholds is not None,
        "weak_classes_analyzed": WEAK_CLASSES,
        "class_summary": {},
    }
    for rec in diagnostics:
        summary["class_summary"][rec["class"]] = {
            "support": rec["support"],
            "f1_global": rec["f1"],
            "f1_tuned": rec.get("f1_tuned"),
            "precision": rec["precision"],
            "recall": rec["recall"],
            "fp": rec["fp"],
            "fn": rec["fn"],
            "probability_separation": rec["probability_separation"],
            "avg_pos_prob": rec["avg_pos_prob"],
            "avg_neg_prob": rec["avg_neg_prob"],
            "diagnosis": rec["diagnosis"],
            "reasoning": rec["reasoning"],
            "recommended_action": rec.get("recommended_action", "N/A"),
        }

    summary_path = DIAGNOSTICS_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n  Saved → {summary_path}")

    # Save report text
    report_path = DIAGNOSTICS_DIR / "report.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"  Saved → {report_path}")

    print("\n" + "=" * 60)
    print("DIAGNOSTIC ANALYSIS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
