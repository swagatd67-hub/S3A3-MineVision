from __future__ import annotations

import csv
import glob
import os
from pathlib import Path


INPUT = Path(
    "approved-data/sewer-ml/coverage_manifest_priority.csv"
)

OUTPUT = Path(
    "approved-data/sewer-ml/coverage_fo_priority.csv"
)

existing = {
    os.path.basename(path)
    for path in glob.glob(
        "approved-data/sewer-ml/images/train00_subset/*.png"
    )
}


def main() -> None:
    with INPUT.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    fo_rows = [
        row
        for row in rows
        if row["FO"] == "1"
        and row["Filename"] not in existing
    ]

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
        writer.writerows(fo_rows)

    print(
        f"FO candidates: {len(fo_rows)}"
    )
    print(
        f"Output: {OUTPUT}"
    )

    print("\nFirst 20:")
    for row in fo_rows[:20]:
        active = [
            key
            for key in (
                "FO",
                "RB",
                "OB",
                "DE",
                "FS",
                "RO",
                "IN",
                "AF",
                "BE",
                "ND",
            )
            if row[key] == "1"
        ]
        print(
            row["Filename"],
            "->",
            ",".join(active),
        )


if __name__ == "__main__":
    main()