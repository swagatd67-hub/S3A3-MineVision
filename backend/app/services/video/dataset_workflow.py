from __future__ import annotations

import hashlib
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from backend.app.services.video.dataset_validator import (
    CLASS_NAMES,
    IMAGE_SUFFIXES,
    validate_dataset,
)


@dataclass(frozen=True)
class DatasetSample:
    image: Path
    label: Path
    sha256: str


@dataclass(frozen=True)
class SplitReport:
    train: int
    val: int
    test: int


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def collect_pairs(
    source_dir: str | Path,
) -> list[tuple[Path, Path]]:
    source = Path(source_dir).resolve()
    images = sorted(
        path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )

    pairs: list[tuple[Path, Path]] = []

    for image in images:
        candidates = [
            image.with_suffix(".txt"),
            image.parent / "labels" / f"{image.stem}.txt",
        ]

        label = next(
            (candidate for candidate in candidates if candidate.exists()),
            None,
        )

        if label is not None:
            pairs.append((image, label))

    return pairs


def split_counts(
    total: int,
    *,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
) -> SplitReport:
    ratios = (train_ratio, val_ratio, test_ratio)

    if any(r < 0 for r in ratios):
        raise ValueError("split ratios cannot be negative")

    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError("split ratios must sum to 1")

    train = int(total * train_ratio)
    val = int(total * val_ratio)
    test = total - train - val

    return SplitReport(train=train, val=val, test=test)


def prepare_split(
    source_dir: str | Path,
    dataset_dir: str | Path = "dataset",
    *,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    seed: int = 42,
    copy_files: bool = True,
) -> SplitReport:
    pairs = collect_pairs(source_dir)

    if not pairs:
        return SplitReport(train=0, val=0, test=0)

    rng = random.Random(seed)
    rng.shuffle(pairs)

    split = split_counts(
        len(pairs),
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
    )

    boundaries = {
        "train": split.train,
        "val": split.train + split.val,
        "test": len(pairs),
    }

    root = Path(dataset_dir).resolve()

    start = 0
    for split_name, end in boundaries.items():
        chunk = pairs[start:end]

        image_root = root / "images" / split_name
        label_root = root / "labels" / split_name

        image_root.mkdir(parents=True, exist_ok=True)
        label_root.mkdir(parents=True, exist_ok=True)

        for image, label in chunk:
            target_image = image_root / image.name
            target_label = label_root / f"{image.stem}.txt"

            if copy_files:
                shutil.copy2(image, target_image)
                shutil.copy2(label, target_label)
            else:
                target_image.write_text(
                    str(image),
                    encoding="utf-8",
                )
                target_label.write_text(
                    str(label),
                    encoding="utf-8",
                )

        start = end

    return split


def class_distribution(
    dataset_dir: str | Path = "dataset",
) -> dict[str, dict[str, int]]:
    root = Path(dataset_dir).resolve()
    distribution: dict[str, dict[str, int]] = {
        name: {
            "train": 0,
            "val": 0,
            "test": 0,
        }
        for name in CLASS_NAMES
    }

    for split in ("train", "val", "test"):
        label_root = root / "labels" / split

        for label_file in label_root.glob("*.txt"):
            for raw in label_file.read_text(
                encoding="utf-8"
            ).splitlines():
                line = raw.strip()

                if not line:
                    continue

                parts = line.split()

                try:
                    class_id = int(parts[0])
                except (ValueError, IndexError):
                    continue

                if 0 <= class_id < len(CLASS_NAMES):
                    distribution[CLASS_NAMES[class_id]][split] += 1

    return distribution


def build_manifest(
    dataset_dir: str | Path = "dataset",
) -> dict:
    root = Path(dataset_dir).resolve()
    report = validate_dataset(root)
    distribution = class_distribution(root)

    images: list[dict[str, str]] = []

    for split in ("train", "val", "test"):
        image_root = root / "images" / split

        for image in sorted(image_root.glob("*")):
            if not image.is_file():
                continue

            if image.suffix.lower() not in IMAGE_SUFFIXES:
                continue

            images.append(
                {
                    "split": split,
                    "file": str(image.relative_to(root)),
                    "sha256": sha256_file(image),
                }
            )

    return {
        "valid": report.valid,
        "images": report.images,
        "labels": report.labels,
        "valid_images": report.valid_images,
        "issue_count": len(report.issues),
        "classes": list(CLASS_NAMES),
        "class_distribution": distribution,
        "images_manifest": images,
    }


def save_manifest(
    dataset_dir: str | Path = "dataset",
    output: str | Path | None = None,
) -> Path:
    root = Path(dataset_dir).resolve()
    output_path = (
        Path(output)
        if output is not None
        else root / "manifest.json"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            build_manifest(root),
            indent=2,
        ),
        encoding="utf-8",
    )

    return output_path
