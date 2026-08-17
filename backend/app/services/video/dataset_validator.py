from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_NAMES = (
    "blockage",
    "debris",
    "crack",
    "corrosion",
    "sediment",
    "structural_damage",
)


@dataclass(frozen=True)
class DatasetIssue:
    split: str
    path: str
    message: str


@dataclass(frozen=True)
class DatasetReport:
    images: int
    labels: int
    valid_images: int
    issues: tuple[DatasetIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def _iter_images(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def _parse_labels(path: Path, split: str) -> list[DatasetIssue]:
    issues: list[DatasetIssue] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return [DatasetIssue(split, str(path), "label file is not UTF-8 text")]

    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 5:
            issues.append(
                DatasetIssue(split, str(path), f"line {number}: expected 5 values")
            )
            continue

        try:
            class_id = int(parts[0])
            x, y, w, h = map(float, parts[1:])
        except ValueError:
            issues.append(
                DatasetIssue(split, str(path), f"line {number}: non-numeric label values")
            )
            continue

        if not 0 <= class_id < len(CLASS_NAMES):
            issues.append(
                DatasetIssue(
                    split, str(path),
                    f"line {number}: class id {class_id} outside 0..{len(CLASS_NAMES)-1}",
                )
            )

        for name, value in (("x_center", x), ("y_center", y), ("width", w), ("height", h)):
            if not 0.0 <= value <= 1.0:
                issues.append(
                    DatasetIssue(
                        split, str(path),
                        f"line {number}: {name}={value} must be between 0 and 1",
                    )
                )

        if w <= 0 or h <= 0:
            issues.append(
                DatasetIssue(split, str(path), f"line {number}: width and height must be > 0")
            )

        if x - w / 2 < 0 or x + w / 2 > 1 or y - h / 2 < 0 or y + h / 2 > 1:
            issues.append(
                DatasetIssue(
                    split, str(path),
                    f"line {number}: bounding box extends outside normalized image bounds",
                )
            )

    return issues


def validate_dataset(dataset_dir: str | Path = "dataset") -> DatasetReport:
    root = Path(dataset_dir).resolve()
    issues: list[DatasetIssue] = []
    total_images = 0
    total_labels = 0
    valid_images = 0

    for split in ("train", "val", "test"):
        image_root = root / "images" / split
        label_root = root / "labels" / split
        images = list(_iter_images(image_root))
        labels = {p.stem: p for p in label_root.glob("*.txt") if p.is_file()}

        total_images += len(images)
        total_labels += len(labels)

        image_stems = {p.stem for p in images}

        for image in images:
            label = labels.get(image.stem)
            if label is None:
                issues.append(
                    DatasetIssue(split, str(image), "missing matching label file")
                )
                continue

            if not cv2.haveImageReader(str(image)):
                issues.append(
                    DatasetIssue(split, str(image), "image cannot be read by OpenCV")
                )
                continue

            if cv2.imread(str(image)) is None:
                issues.append(
                    DatasetIssue(split, str(image), "image is unreadable or empty")
                )
                continue

            label_issues = _parse_labels(label, split)
            issues.extend(label_issues)

            if not label_issues:
                valid_images += 1

        for stem, label in sorted(labels.items()):
            if stem not in image_stems:
                issues.append(
                    DatasetIssue(split, str(label), "label has no matching image")
                )

    return DatasetReport(
        images=total_images,
        labels=total_labels,
        valid_images=valid_images,
        issues=tuple(issues),
    )
