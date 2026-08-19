from __future__ import annotations

import csv
import glob
import os
from pathlib import Path


CSV_PATH = Path(
    "approved-data/sewer-ml/extracted/SewerML_Train.csv"
)

CANDIDATES = Path(
    "approved-data/sewer-ml/coverage_manifest_priority.csv"
)

IMAGE_DIR = Path(
    "approved-data/sewer-ml/images/train00_subset"
)

OUTPUT = Path(
    "approved-data/sewer-ml/next_batch_manifest.csv"
)

CLASSES = [
    "RB",
    "OB",
    "PF",
    "DE",
    "FS",
    "IS",
    "RO",
    "IN",
    "AF",
    "BE",
    "FO",
    "GR",
    "PH",
    "PB",
    "OS",
    "OP",
    "OK",
]

TARGETS = {
    "RB": 80,
    "OB": 100,
    "PF": 80,
    "DE": 80,
    "FS": 100,
    "IS": 40,
    "RO": 40,
    "IN": 60,
    "AF": 80,
    "BE": 100,
    "FO": 40,
    "GR": 40,
    "PH": 40,
    "PB": 8,
    "OS": 40,
    "OP": 12,
    "OK": 40,
}

BATCH_SIZE = 10


def load_csv_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return {
            row["Filename"]: row
            for row in csv.DictReader(handle)
        }


def get_existing_files() -> set[str]:
    return {
        os.path.basename(path)
        for path in glob.glob(
            str(IMAGE_DIR / "*.png")
        )
    }


def calculate_current_coverage(
    rows: dict[str, dict[str, str]],
    existing: set[str],
) -> dict[str, int]:
    counts = {
        cls: 0
        for cls in CLASSES
    }

    for filename in existing:
        row = rows.get(filename)

        if row is None:
            continue

        for cls in CLASSES:
            if row[cls] == "1":
                counts[cls] += 1

    return counts


def class_weight(
    cls: str,
    current: int,
) -> float:
    target = TARGETS[cls]

    if current >= target:
        return 0.0

    deficit = target - current
    ratio = deficit / target

    if current == 0:
        return 20.0

    if current <= 2:
        return 15.0

    if current <= 5:
        return 12.0

    if current <= 10:
        return 9.0

    return 2.0 + 8.0 * ratio


def score_row(
    row: dict[str, str],
    current: dict[str, int],
) -> float:
    score = 0.0
    useful = 0

    for cls in CLASSES:
        if row[cls] != "1":
            continue

        weight = class_weight(
            cls,
            current[cls],
        )

        if weight <= 0:
            continue

        score += weight
        useful += 1

    # Strong reward for useful multi-label images.
    if useful >= 2:
        score += 5.0 * useful

    return score


def main() -> None:
    metadata = load_csv_rows(CSV_PATH)

    existing = get_existing_files()

    current = calculate_current_coverage(
        metadata,
        existing,
    )

    with CANDIDATES.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        candidate_rows = list(
            csv.DictReader(handle)
        )

    # Absolutely exclude anything already on disk.
    candidates = [
        row
        for row in candidate_rows
        if row["Filename"] not in existing
    ]

    scored = [
        (
            score_row(row, current),
            row,
        )
        for row in candidates
    ]

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1]["Filename"],
        )
    )

    selected = [
        row
        for _, row in scored[:BATCH_SIZE]
    ]

    if not selected:
        print("No new candidate images available.")
        return

    with OUTPUT.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=selected[0].keys(),
        )
        writer.writeheader()
        writer.writerows(selected)

    print("Actual current coverage:")
    for cls in CLASSES:
        print(
            f"  {cls}: "
            f"{current[cls]} / "
            f"{TARGETS[cls]}"
        )

    print()
    print(
        f"Next batch: {len(selected)} images"
    )

    print(
        f"Manifest: {OUTPUT}"
    )

    print()
    print("Selected:")

    for row in selected:
        labels = [
            cls
            for cls in CLASSES
            if row[cls] == "1"
        ]

        print(
            row["Filename"],
            "->",
            ",".join(labels),
        )


if __name__ == "__main__":
    main()