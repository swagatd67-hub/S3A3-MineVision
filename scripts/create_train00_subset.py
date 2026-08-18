from __future__ import annotations

import csv
import random
from pathlib import Path


TRAIN_CSV = Path("approved-data/sewer-ml/extracted/SewerML_Train.csv")
TRAIN00_FILES = Path("approved-data/sewer-ml/images/train00-files.txt")
OUTPUT_CSV = Path("approved-data/sewer-ml/train00_subset.csv")

# Keep all examples for rare classes in train00, and cap common classes.
TARGETS = {
    "RB": 2000,
    "OB": 2000,
    "DE": 318,   # keep all available in train00
    "FS": 2000,
    "RO": 930,   # keep all available in train00
    "IN": 161,   # keep all available in train00
    "AF": 2000,
    "BE": 2000,
    "FO": 235,   # keep all available in train00
    "ND": 2000,
}

SEED = 42


def main() -> None:
    archive_files = {
        name.strip()
        for name in TRAIN00_FILES.read_text(encoding="utf-8").splitlines()
        if name.strip()
    }

    with TRAIN_CSV.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["Filename"] in archive_files
        ]

    print(f"Rows matched to train00: {len(rows)}")

    buckets: dict[str, list[dict[str, str]]] = {
        label: []
        for label in TARGETS
    }

    for row in rows:
        for label in TARGETS:
            if row[label] == "1":
                buckets[label].append(row)

    rng = random.Random(SEED)

    selected: dict[str, dict[str, str]] = {}

    for label, limit in TARGETS.items():
        candidates = buckets[label].copy()
        rng.shuffle(candidates)

        for row in candidates[:limit]:
            selected[row["Filename"]] = row

        print(
            f"{label}: available={len(candidates)} "
            f"target={min(limit, len(candidates))}"
        )

    output_rows = sorted(
        selected.values(),
        key=lambda row: row["Filename"],
    )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with TRAIN_CSV.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        fieldnames = csv.DictReader(handle).fieldnames

    if not fieldnames:
        raise RuntimeError("Training CSV has no header")

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print()
    print(f"Unique selected images: {len(output_rows)}")
    print(f"Manifest: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
