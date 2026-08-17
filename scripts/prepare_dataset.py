from __future__ import annotations

import argparse
import json

from backend.app.services.video.dataset_workflow import (
    build_manifest,
    prepare_split,
    save_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a PipeVision YOLO dataset"
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Directory containing approved image/label pairs",
    )

    parser.add_argument(
        "--dataset-dir",
        default="dataset",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    split = prepare_split(
        args.source,
        args.dataset_dir,
        seed=args.seed,
    )

    manifest_path = save_manifest(args.dataset_dir)

    print(
        json.dumps(
            {
                "split": {
                    "train": split.train,
                    "val": split.val,
                    "test": split.test,
                },
                "manifest": str(manifest_path),
                "summary": build_manifest(args.dataset_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
