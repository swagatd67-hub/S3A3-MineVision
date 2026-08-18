from __future__ import annotations

import csv
import glob
import json
import os
import random
from pathlib import Path


CSV_PATH = Path(
    "approved-data/sewer-ml/extracted/SewerML_Train.csv"
)

PLAN_PATH = Path(
    "approved-data/sewer-ml/train00_download_plan.json"
)

OUTPUT_PATH = Path(
    "approved-data/sewer-ml/coverage_manifest.csv"
)

TARGETS = {
    "RB": 800,
    "OB": 1000,
    "DE": 500,
    "FS": 1000,
    "RO": 500,
    "IN": 300,
    "AF": 800,
    "BE": 1000,
    "FO": 300,
    "ND": 1000,
}

SEED = 42


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def load_plan() -> set[str]:
    payload = json.loads(
        PLAN_PATH.read_text(
            encoding="utf-8"
        )
    )

    return {
        entry["filename"]
        for entry in payload["entries"]
    }


def current_files() -> set[str]:
    return {
        os.path.basename(path)
        for path in glob.glob(
            "approved-data/sewer-ml/"
            "images/train00_subset/*.png"
        )
    }


def main() -> None:
    rows = load_rows()
    available = load_plan()
    existing = current_files()

    rows = [
        row
        for row in rows
        if row["Filename"] in available
    ]

    random.seed(SEED)

    buckets = {
        label: []
        for label in TARGETS
    }

    for row in rows:
        filename = row["Filename"]

        if filename in existing:
            continue

        for label in TARGETS:
            if row[label] == "1":
                buckets[label].append(row)

    for bucket in buckets.values():
        random.shuffle(bucket)

    selected: dict[str, dict[str, str]] = {}

    current_counts = {
        label: 0
        for label in TARGETS
    }

    # Count what we already have.
    for row in rows:
        if row["Filename"] not in existing:
            continue

        for label in TARGETS:
            if row[label] == "1":
                current_counts[label] += 1

    print("Current coverage:")
    for label in TARGETS:
        print(
            f"  {label}: "
            f"{current_counts[label]} / "
            f"{TARGETS[label]}"
        )

    # First satisfy the rare/under-covered classes.
    labels_by_need = sorted(
        TARGETS,
        key=lambda label: (
            current_counts[label]
            / TARGETS[label]
            if TARGETS[label]
            else 1.0
        ),
    )

    for label in labels_by_need:
        needed = max(
            0,
            TARGETS[label]
            - current_counts[label],
        )

        taken = 0

        for row in buckets[label]:
            filename = row["Filename"]

            if filename in selected:
                continue

            # Don't add an image that provides no benefit
            # to any currently under-covered target.
            useful = any(
                row[target] == "1"
                and current_counts[target]
                + sum(
                    1
                    for chosen in selected.values()
                    if chosen[target] == "1"
                )
                < TARGETS[target]
                for target in TARGETS
            )

            if not useful:
                continue

            selected[filename] = row
            taken += 1

            if taken >= needed:
                break

    output_rows = sorted(
        selected.values(),
        key=lambda row: row["Filename"],
    )

    with OUTPUT_PATH.open(
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
        writer.writerows(output_rows)

    print()
    print(
        "New images requested:",
        len(output_rows),
    )

    print(
        "Manifest:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()