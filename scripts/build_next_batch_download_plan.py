from __future__ import annotations

import csv
import json
from pathlib import Path


MANIFEST = Path(
    "approved-data/sewer-ml/next_batch_manifest.csv"
)

MASTER_PLAN = Path(
    "approved-data/sewer-ml/train00_download_plan.json"
)

OUTPUT = Path(
    "approved-data/sewer-ml/next_batch_download_plan.json"
)


def main() -> None:
    with MANIFEST.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        selected = [
            row["Filename"]
            for row in csv.DictReader(handle)
        ]

    master = json.loads(
        MASTER_PLAN.read_text(
            encoding="utf-8"
        )
    )

    by_name = {
        entry["filename"]: entry
        for entry in master["entries"]
    }

    missing = [
        filename
        for filename in selected
        if filename not in by_name
    ]

    if missing:
        raise RuntimeError(
            f"{len(missing)} selected files are missing "
            f"from the master plan: {missing[:10]}"
        )

    entries = [
        by_name[filename]
        for filename in selected
    ]

    compressed_total = sum(
        entry["compressed_size"]
        for entry in entries
    )

    payload = {
        "archive": master["archive"],
        "archive_size": master["archive_size"],
        "selected_files": len(entries),
        "compressed_payload_bytes": compressed_total,
        "compressed_payload_mib": round(
            compressed_total / (1024 ** 2),
            2,
        ),
        "entries": entries,
    }

    OUTPUT.write_text(
        json.dumps(
            payload,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Selected files: {len(entries)}"
    )

    print(
        "Compressed payload:",
        payload["compressed_payload_mib"],
        "MiB",
    )

    print(
        f"Plan: {OUTPUT}"
    )

    print("\nFiles:")
    for entry in entries:
        print(
            entry["filename"],
            entry["compressed_size"],
            "bytes",
        )


if __name__ == "__main__":
    main()