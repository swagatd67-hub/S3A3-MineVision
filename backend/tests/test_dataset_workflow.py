from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.app.services.video.dataset_workflow import (
    build_manifest,
    class_distribution,
    collect_pairs,
    prepare_split,
    split_counts,
)


def write_sample_pair(root: Path, stem: str, class_id: int = 0) -> None:
    root.mkdir(parents=True, exist_ok=True)

    image = np.full(
        (64, 64, 3),
        128,
        dtype=np.uint8,
    )

    image_path = root / f"{stem}.png"
    label_path = root / f"{stem}.txt"

    assert cv2.imwrite(
        str(image_path),
        image,
    )

    label_path.write_text(
        f"{class_id} 0.5 0.5 0.4 0.4\n",
        encoding="utf-8",
    )


def test_collect_pairs(tmp_path):
    write_sample_pair(
        tmp_path,
        "pipe_001",
    )

    pairs = collect_pairs(tmp_path)

    assert len(pairs) == 1
    assert pairs[0][0].stem == "pipe_001"
    assert pairs[0][1].stem == "pipe_001"


def test_split_counts():
    result = split_counts(10)

    assert result.train == 7
    assert result.val == 2
    assert result.test == 1


def test_invalid_ratios_rejected():
    with pytest.raises(ValueError):
        split_counts(
            10,
            train_ratio=0.8,
            val_ratio=0.3,
            test_ratio=-0.1,
        )


def test_prepare_split(tmp_path):
    source = tmp_path / "source"
    dataset = tmp_path / "dataset"

    for index in range(10):
        write_sample_pair(
            source,
            f"pipe_{index:03d}",
        )

    report = prepare_split(
        source,
        dataset,
        seed=42,
    )

    assert report.train == 7
    assert report.val == 2
    assert report.test == 1

    assert len(list((dataset / "images/train").glob("*"))) == 7
    assert len(list((dataset / "images/val").glob("*"))) == 2
    assert len(list((dataset / "images/test").glob("*"))) == 1


def test_class_distribution(tmp_path):
    dataset = tmp_path / "dataset"

    write_sample_pair(
        dataset / "images/train",
        "pipe_001",
        class_id=2,
    )

    # Move corresponding label into YOLO label tree.
    label_source = dataset / "images/train/pipe_001.txt"
    label_target = dataset / "labels/train/pipe_001.txt"
    label_target.parent.mkdir(parents=True, exist_ok=True)
    label_target.write_text(
        label_source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    label_source.unlink()

    distribution = class_distribution(dataset)

    assert distribution["crack"]["train"] == 1


def test_manifest_contains_hashes(tmp_path):
    dataset = tmp_path / "dataset"

    write_sample_pair(
        dataset / "images/train",
        "pipe_001",
        class_id=0,
    )

    source_label = dataset / "images/train/pipe_001.txt"
    target_label = dataset / "labels/train/pipe_001.txt"
    target_label.parent.mkdir(parents=True, exist_ok=True)
    target_label.write_text(
        source_label.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    source_label.unlink()

    manifest = build_manifest(dataset)

    assert manifest["images"] == 1
    assert manifest["images_manifest"][0]["sha256"]
