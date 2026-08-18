from __future__ import annotations

import csv
import json
from pathlib import Path


COVERAGE_CSV = Path(
    "approved-data/sewer-ml/coverage_manifest.csv"
)

DOWNLOAD_PLAN = Path(
    "approved-data/sewer-ml/train00_download_plan.json"
)

OUTPUT = Path(
    "approved-data/sewer-ml/coverage_download_plan.json"
)


def main() -> None:
    selected = {
        row["Filename"]
        for row in csv.DictReader(
            COVERAGE_CSV.open(
                encoding="utf-8-sig",
                newline="",
            )
        )
    }

    plan = json.loads(
        DOWNLOAD_PLAN.read_text(
            encoding="utf-8"
        )
    )

    entries = [
        entry
        for entry in plan["entries"]
        if entry["filename"] in selected
    ]

    if len(entries) != len(selected):
        missing = selected - {
            entry["filename"]
            for entry in entries
        }

        raise RuntimeError(
            f"{len(missing)} coverage files are missing "
            f"from train00_download_plan.json. "
            f"Examples: {sorted(missing)[:10]}"
        )

    OUTPUT.write_text(
        json.dumps(
            {
                "archive": plan["archive"],
                "archive_size": plan["archive_size"],
                "selected_files": len(entries),
                "compressed_payload_bytes": sum(
                    entry["compressed_size"]
                    for entry in entries
                ),
                "entries": sorted(
                    entries,
                    key=lambda entry: entry["filename"],
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Coverage files: {len(entries)}"
    )

    print(
        "Compressed payload:",
        round(
            sum(
                entry["compressed_size"]
                for entry in entries
            ) / (1024 ** 3),
            2,
        ),
        "GiB",
    )

    print(
        f"Plan: {OUTPUT}"
    )


if __name__ == "__main__":
    main()