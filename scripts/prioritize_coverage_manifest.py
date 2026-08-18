from __future__ import annotations

import csv
from pathlib import Path


INPUT = Path(
    "approved-data/sewer-ml/coverage_manifest.csv"
)

OUTPUT = Path(
    "approved-data/sewer-ml/coverage_manifest_priority.csv"
)

PRIORITY = {
    "IN": 0,
    "FO": 1,
    "IS": 2,
    "OS": 3,
    "OP": 4,
    "RO": 5,
    "DE": 6,
    "RB": 7,
    "AF": 8,
    "OB": 9,
    "FS": 10,
    "BE": 11,
    "ND": 12,
}


def row_priority(row: dict[str, str]) -> tuple[int, int, str]:
    labels = [
        label
        for label in PRIORITY
        if row[label] == "1"
    ]

    if not labels:
        return (999, 999, row["Filename"])

    best = min(
        PRIORITY[label]
        for label in labels
    )

    # Count how many high-priority labels this image covers.
    coverage = sum(
        row[label] == "1"
        for label in PRIORITY
    )

    return (
        best,
        -coverage,
        row["Filename"],
    )


def main() -> None:
    with INPUT.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(
            csv.DictReader(handle)
        )

    rows.sort(
        key=row_priority
    )

    with OUTPUT.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=rows[0].keys(),
        )
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"Priority manifest: {len(rows)} images"
    )
    print(
        f"Output: {OUTPUT}"
    )

    print("\nFirst 25:")
    for row in rows[:25]:
        active = [
            label
            for label in PRIORITY
            if row[label] == "1"
        ]
        print(
            row["Filename"],
            "->",
            ",".join(active),
        )


if __name__ == "__main__":
    main()