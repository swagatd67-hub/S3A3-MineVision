from __future__ import annotations

import csv
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image

from backend.app.services.video.sewer_dataset import DEFECT_CLASSES


IMAGE_DIR = Path("approved-data/sewer-ml/images/train00_subset")
CSV_PATH = Path("approved-data/sewer-ml/extracted/SewerML_Train.csv")
TRAIN_SPLIT = Path("approved-data/sewer-ml/splits/train.csv")
VAL_SPLIT = Path("approved-data/sewer-ml/splits/val.csv")


def verify_integrity() -> None:
    print("--- Verifying Dataset & Split Integrity ---")

    # 1. Train manifest exists
    if not TRAIN_SPLIT.exists():
        raise FileNotFoundError(f"Train split manifest missing: {TRAIN_SPLIT}")
    print(f"[OK] Train split exists: {TRAIN_SPLIT}")

    # 2. Validation manifest exists
    if not VAL_SPLIT.exists():
        raise FileNotFoundError(f"Val split manifest missing: {VAL_SPLIT}")
    print(f"[OK] Val split exists: {VAL_SPLIT}")

    # Read train & val manifests
    def read_manifest(path: Path) -> tuple[list[str], list[dict[str, str]]]:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            headers: list[str] = list(reader.fieldnames or [])
            rows: list[dict[str, str]] = list(reader)
        return headers, rows

    train_headers, train_rows = read_manifest(TRAIN_SPLIT)
    val_headers, val_rows = read_manifest(VAL_SPLIT)

    # 5. Number of labels is 17 & 7. Class names match DEFECT_CLASSES
    train_class_headers = [h for h in train_headers if h != "Filename"]
    val_class_headers = [h for h in val_headers if h != "Filename"]

    if train_class_headers != DEFECT_CLASSES:
        raise ValueError(f"Train split headers do not match DEFECT_CLASSES: {train_class_headers}")
    if val_class_headers != DEFECT_CLASSES:
        raise ValueError(f"Val split headers do not match DEFECT_CLASSES: {val_class_headers}")

    if len(DEFECT_CLASSES) != 17:
        raise ValueError(f"Expected 17 classes, got {len(DEFECT_CLASSES)}")

    print(f"[OK] Manifest headers match expected 17 DEFECT_CLASSES: {DEFECT_CLASSES}")

    train_filenames = [r["Filename"] for r in train_rows]
    val_filenames = [r["Filename"] for r in val_rows]

    print(f"Train count: {len(train_filenames)}, Val count: {len(val_filenames)}")

    # 4. No duplicate filenames between train and val
    train_set = set(train_filenames)
    val_set = set(val_filenames)
    overlap = train_set.intersection(val_set)
    if overlap:
        raise ValueError(f"Data leakage detected! Filename overlap between train and val: {overlap}")
    print("[OK] Train and Validation sets have zero overlap (Data Leakage Check passed).")

    # 6. All labels are binary (0 or 1)
    for name, rows in [("train", train_rows), ("val", val_rows)]:
        for row in rows:
            for cls in DEFECT_CLASSES:
                val_str = row[cls]
                if val_str not in ("0", "1"):
                    raise ValueError(f"Non-binary label '{val_str}' in {name} row {row['Filename']} for class {cls}")
    print("[OK] All class labels in train and val manifests are strictly binary (0 or 1).")

    # 3. All images exist and can be loaded
    all_filenames = sorted(list(train_set.union(val_set)))
    print(f"Verifying readability of all {len(all_filenames)} images...")
    for filename in all_filenames:
        img_path = IMAGE_DIR / filename
        if not img_path.exists():
            raise FileNotFoundError(f"Image file missing: {img_path}")
        try:
            with Image.open(img_path) as img:
                img.verify()
        except Exception as e:
            raise RuntimeError(f"Corrupt or unreadable image {img_path}: {e}")

    print(f"[OK] All {len(all_filenames)} images successfully loaded and verified.")
    print("=== DATA INTEGRITY VERIFICATION COMPLETE & PASSED ===")


if __name__ == "__main__":
    try:
        verify_integrity()
    except Exception as err:
        print(f"INTEGRITY CHECK FAILED: {err}", file=sys.stderr)
        sys.exit(1)
