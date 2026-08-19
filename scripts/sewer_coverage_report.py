from __future__ import annotations

import csv
import glob
from pathlib import Path

from backend.app.services.video.sewer_dataset import (
    DEFECT_CLASSES,
)


CSV_PATH = Path(
    "approved-data/sewer-ml/extracted/SewerML_Train.csv"
)

IMAGE_DIR = Path(
    "approved-data/sewer-ml/images/train00_subset"
)

TARGETS = {
    "RB": 500,
    "OB": 500,
    "PF": 300,
    "DE": 500,
    "FS": 500,
    "IS": 300,
    "RO": 300,
    "IN": 300,
    "AF": 500,
    "BE": 500,
    "FO": 300,
    "GR": 300,
    "PH": 300,
    "PB": 300,
    "OS": 300,
    "OP": 300,
    "OK": 300,
}


def main() -> None:
    available_files = {
        Path(path).name
        for path in glob.glob(
            str(IMAGE_DIR / "*.png")
        )
    }

    with CSV_PATH.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    rows = [
        row
        for row in rows
        if row["Filename"] in available_files
    ]

    print(
        f"Downloaded images: {len(rows)}"
    )

    print()
    print(
        f"{'CLASS':<6}"
        f"{'AVAILABLE':>12}"
        f"{'TARGET':>10}"
        f"{'GAP':>10}"
        f"{'COVERAGE':>12}"
    )

    print("-" * 52)

    for class_name in DEFECT_CLASSES:
        available = sum(
            row[class_name] == "1"
            for row in rows
        )

        target = TARGETS.get(
            class_name,
            0,
        )

        gap = max(
            0,
            target - available,
        )

        coverage = (
            available / target
            if target
            else 0.0
        )

        print(
            f"{class_name:<6}"
            f"{available:>12}"
            f"{target:>10}"
            f"{gap:>10}"
            f"{coverage:>11.1%}"
        )


if __name__ == "__main__":
    main()