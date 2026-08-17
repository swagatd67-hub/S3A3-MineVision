import cv2
import numpy as np
import pytest

from backend.app.services.video.preprocessing import (
    PreprocessConfig,
    preprocess_frame,
    quality_summary,
)


def make_test_image(width: int = 1600, height: int = 900) -> np.ndarray:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.rectangle(image, (100, 100), (width - 100, height - 100), 220, 8)
    cv2.line(image, (100, 100), (width - 100, height - 100), 40, 6)
    cv2.line(image, (width - 100, 100), (100, height - 100), 40, 6)
    cv2.putText(
        image,
        "PIPEVISION",
        (180, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        4,
        255,
        8,
        cv2.LINE_AA,
    )
    return image


def test_preprocessing_resizes_and_returns_quality_metrics():
    image = make_test_image()
    result = preprocess_frame(image, PreprocessConfig(target_width=800))

    assert result.original_width == 1600
    assert result.original_height == 900
    assert result.processed_width == 800
    assert result.processed_height == 450
    assert result.image.shape[:2] == (450, 800)
    assert result.blur_score >= 0
    assert result.brightness >= 0
    assert result.contrast >= 0


def test_quality_summary_is_frontend_ready():
    image = make_test_image(640, 360)
    result = preprocess_frame(image)
    summary = quality_summary(result)

    assert summary["original_size"]["width"] == 640
    assert summary["processed_size"]["width"] == 640
    assert "blur_score" in summary
    assert "brightness" in summary
    assert "contrast" in summary
    assert "usable_for_ai" in summary


def test_invalid_image_rejected():
    with pytest.raises(ValueError):
        preprocess_frame(np.array([]))


def test_bad_kernel_rejected():
    image = make_test_image(320, 180)
    with pytest.raises(ValueError):
        preprocess_frame(image, PreprocessConfig(gaussian_kernel=4))
