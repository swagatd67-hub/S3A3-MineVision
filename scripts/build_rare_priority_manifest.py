from __future__ import annotations

import csv
import os
from pathlib import Path


INPUT = Path(
    "approved-data/sewer-ml/smart_coverage_manifest.csv"
)

OUTPUT = Path(
    "approved-data/sewer-ml/rare_priority_manifest.csv"
)

PRIORITY = {
    "PB": 100,
    "IS": 95,
    "OS": 95,
    "OP": 90,
    "RO": 85,
    "FO": 85,
    "GR": 80,
    "PH": 80,
    "DE": 70,
    "RB": 70,
    "AF": 65,
    "IN": 55,
    "OB": 45,
    "FS": 40,
    "BE": 35,
    "PF": 30,
    "OK": 25,
}

LIMIT = 100


def row_score(row: dict[str, str]) -> float:
    labels = [
        label
        for label, weight in PRIORITY.items()
        if row[label] == "1"
    ]

    if not labels:
        return 0.0

    score = sum(
        PRIORITY[label]
        for label in labels
    )

    # Reward multi-label images because one download
    # improves several classes simultaneously.
    if len(labels) > 1:
        score += 10 * (len(labels) - 1)

    return score


def main() -> None:
    with INPUT.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        row["_score"] = row_score(row)

    rows.sort(
        key=lambda row: (
            -float(row["_score"]),
            row["Filename"],
        )
    )

    selected = rows[:LIMIT]

    if "_score" in selected[0]:
        for row in selected:
            del row["_score"]

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

    print("\nFirst 30:")
    for row in selected[:30]:
        labels = [
            label
            for label in PRIORITY
            if row[label] == "1"
        ]

        print(
            row["Filename"],
            "->",
            ",".join(labels),
        )


if __name__ == "__main__":
    main()