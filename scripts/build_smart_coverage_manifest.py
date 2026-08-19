from __future__ import annotations

import csv
import glob
import os
from pathlib import Path


INPUT = Path(
    "approved-data/sewer-ml/coverage_manifest_priority.csv"
)

OUTPUT = Path(
    "approved-data/sewer-ml/smart_coverage_manifest.csv"
)

IMAGE_DIR = Path(
    "approved-data/sewer-ml/images/train00_subset"
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
    "PB": 40,
    "OS": 40,
    "OP": 40,
    "OK": 40,
}


def load_rows() -> list[dict[str, str]]:
    with INPUT.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def existing_files() -> set[str]:
    return {
        os.path.basename(path)
        for path in glob.glob(
            str(IMAGE_DIR / "*.png")
        )
    }


def count_current(
    rows: list[dict[str, str]],
    existing: set[str],
) -> dict[str, int]:
    counts = {
        class_name: 0
        for class_name in CLASSES
    }

    for row in rows:
        if row["Filename"] not in existing:
            continue

        for class_name in CLASSES:
            if row[class_name] == "1":
                counts[class_name] += 1

    return counts


def build_weights(
    counts: dict[str, int],
) -> dict[str, float]:
    weights: dict[str, float] = {}

    for class_name in CLASSES:
        target = TARGETS[class_name]
        current = counts[class_name]

        if current >= target:
            weights[class_name] = 0.05
            continue

        deficit_ratio = (
            target - current
        ) / target

        # Larger weight for bigger deficits.
        # Floor prevents any useful class from becoming zero.
        weights[class_name] = max(
            0.25,
            1.0 + 4.0 * deficit_ratio,
        )

    return weights


def score_row(
    row: dict[str, str],
    counts: dict[str, int],
    weights: dict[str, float],
) -> float:
    score = 0.0

    labels = [
        class_name
        for class_name in CLASSES
        if row[class_name] == "1"
    ]

    for class_name in labels:
        current = counts[class_name]
        target = TARGETS[class_name]

        if current >= target:
            continue

        deficit_ratio = (
            target - current
        ) / target

        # Prioritize classes with larger deficits.
        score += (
            weights[class_name]
            * (1.0 + deficit_ratio)
        )

    # Bonus for covering multiple useful classes.
    useful_labels = [
        class_name
        for class_name in labels
        if counts[class_name] < TARGETS[class_name]
    ]

    score += 0.75 * max(
        0,
        len(useful_labels) - 1,
    )

    return score


def main() -> None:
    rows = load_rows()
    existing = existing_files()

    candidates = [
        row
        for row in rows
        if row["Filename"] not in existing
    ]

    current = count_current(
        rows,
        existing,
    )

    weights = build_weights(current)

    print("Current coverage:")
    for class_name in CLASSES:
        print(
            f"  {class_name}: "
            f"{current[class_name]} / "
            f"{TARGETS[class_name]}"
        )

    selected: list[dict[str, str]] = []
    remaining = candidates.copy()

    # Greedy selection.
    #
    # At each step choose the candidate with
    # the highest value for currently under-covered classes.
    #
    # Stop when every target is satisfied or
    # candidates are exhausted.
    while remaining:
        best_index = None
        best_score = 0.0

        for index, row in enumerate(remaining):
            score = score_row(
                row,
                current,
                weights,
            )

            if score > best_score:
                best_score = score
                best_index = index

        if best_index is None or best_score <= 0:
            break

        row = remaining.pop(best_index)

        selected.append(row)

        for class_name in CLASSES:
            if row[class_name] == "1":
                current[class_name] += 1

        # Check whether all targets are reached.
        if all(
            current[class_name]
            >= TARGETS[class_name]
            for class_name in CLASSES
        ):
            break

    with OUTPUT.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = rows[0].keys()

        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(selected)

    print()
    print(
        "Smart candidates selected:",
        len(selected),
    )

    print()
    print("Projected coverage:")

    for class_name in CLASSES:
        print(
            f"  {class_name}: "
            f"{current[class_name]} / "
            f"{TARGETS[class_name]}"
        )

    print()
    print(
        "Output:",
        OUTPUT,
    )

    print()
    print("First 30:")
    for row in selected[:30]:
        labels = [
            class_name
            for class_name in CLASSES
            if row[class_name] == "1"
        ]

        print(
            row["Filename"],
            "->",
            ",".join(labels),
        )


if __name__ == "__main__":
    main()