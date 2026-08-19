from __future__ import annotations

import csv
import glob
import os
from pathlib import Path

CSV_PATH = Path(
    "approved-data/sewer-ml/coverage_manifest_priority.csv"
)

IMAGE_DIR = Path(
    "approved-data/sewer-ml/images/train00_subset"
)

OUTPUT = Path(
    "approved-data/sewer-ml/final_rare_manifest.csv"
)

PRIORITY = {
    "PB": 100,
    "OP": 95,
    "IS": 90,
    "OS": 90,
}

MAX_FILES = 40


def main() -> None:
    existing = {
        os.path.basename(path)
        for path in glob.glob(
            str(IMAGE_DIR / "*.png")
        )
    }

    with CSV_PATH.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    candidates = [
        row
        for row in rows
        if row["Filename"] not in existing
    ]

    scored = []

    for row in candidates:
        labels = [
            cls
            for cls in PRIORITY
            if row[cls] == "1"
        ]

        if not labels:
            continue

        score = sum(
            PRIORITY[label]
            for label in labels
        )

        # Reward images covering multiple rare classes.
        if len(labels) > 1:
            score += 20 * (len(labels) - 1)

        scored.append(
            (score, row)
        )

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1]["Filename"],
        )
    )

    selected = [
        row
        for _, row in scored[:MAX_FILES]
    ]

    if not selected:
        raise RuntimeError(
            "No remaining rare-class candidates found."
        )

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

    print(
        "Selected:",
        len(selected),
    )

    print(
        "Output:",
        OUTPUT,
    )

    print("\nSelected files:")

    for row in selected:
        labels = [
            cls
            for cls in PRIORITY
            if row[cls] == "1"
        ]

        print(
            row["Filename"],
            "->",
            ",".join(labels),
        )


if __name__ == "__main__":
    main()