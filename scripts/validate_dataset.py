from __future__ import annotations

import argparse
import json

from backend.app.services.video.dataset_validator import validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate PipeVision YOLO dataset")
    parser.add_argument("--dataset-dir", default="dataset")
    args = parser.parse_args()

    report = validate_dataset(args.dataset_dir)

    print(json.dumps({
        "valid": report.valid,
        "images": report.images,
        "labels": report.labels,
        "valid_images": report.valid_images,
        "issue_count": len(report.issues),
        "issues": [
            {"split": i.split, "path": i.path, "message": i.message}
            for i in report.issues
        ],
    }, indent=2))

    raise SystemExit(0 if report.valid else 1)


if __name__ == "__main__":
    main()
