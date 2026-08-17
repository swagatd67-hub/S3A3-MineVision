from pathlib import Path

import cv2
import numpy as np

from backend.app.services.video.dataset_validator import validate_dataset


def make_dataset(root: Path) -> None:
    for split in ("train", "val", "test"):
        (root / "images" / split).mkdir(parents=True, exist_ok=True)
        (root / "labels" / split).mkdir(parents=True, exist_ok=True)


def write_image(path: Path) -> None:
    image = np.full((100, 120, 3), 128, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def test_valid_dataset(tmp_path):
    make_dataset(tmp_path)
    image = tmp_path / "images/train/pipe_001.png"
    label = tmp_path / "labels/train/pipe_001.txt"
    write_image(image)
    label.write_text("0 0.5 0.5 0.4 0.4\n", encoding="utf-8")

    report = validate_dataset(tmp_path)

    assert report.valid
    assert report.images == 1
    assert report.labels == 1
    assert report.valid_images == 1


def test_missing_label_is_reported(tmp_path):
    make_dataset(tmp_path)
    write_image(tmp_path / "images/train/pipe_002.png")

    report = validate_dataset(tmp_path)

    assert not report.valid
    assert any("missing matching label" in i.message for i in report.issues)


def test_invalid_class_is_reported(tmp_path):
    make_dataset(tmp_path)
    image = tmp_path / "images/train/pipe_003.png"
    label = tmp_path / "labels/train/pipe_003.txt"
    write_image(image)
    label.write_text("9 0.5 0.5 0.4 0.4\n", encoding="utf-8")

    report = validate_dataset(tmp_path)

    assert not report.valid
    assert any("class id 9" in i.message for i in report.issues)


def test_bad_coordinates_are_reported(tmp_path):
    make_dataset(tmp_path)
    image = tmp_path / "images/train/pipe_004.png"
    label = tmp_path / "labels/train/pipe_004.txt"
    write_image(image)
    label.write_text("1 1.2 0.5 0.4 0.4\n", encoding="utf-8")

    report = validate_dataset(tmp_path)

    assert not report.valid
    assert any("must be between 0 and 1" in i.message for i in report.issues)


def test_orphan_label_is_reported(tmp_path):
    make_dataset(tmp_path)
    label = tmp_path / "labels/train/orphan.txt"
    label.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    report = validate_dataset(tmp_path)

    assert not report.valid
    assert any("no matching image" in i.message for i in report.issues)
