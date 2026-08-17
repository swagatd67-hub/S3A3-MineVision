from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class PreprocessConfig:
    target_width: int = 1280
    gaussian_kernel: int = 3
    clahe_clip_limit: float = 2.0
    clahe_grid_size: tuple[int, int] = (8, 8)
    min_blur_score: float = 30.0
    min_brightness: float = 25.0
    max_brightness: float = 230.0
    min_contrast: float = 15.0


@dataclass(frozen=True)
class PreprocessedFrame:
    image: np.ndarray
    original_width: int
    original_height: int
    processed_width: int
    processed_height: int
    blur_score: float
    brightness: float
    contrast: float
    usable_for_ai: bool
    quality_reasons: tuple[str, ...]


def preprocess_frame(
    image: np.ndarray,
    config: PreprocessConfig | None = None,
) -> PreprocessedFrame:
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("image must be a non-empty numpy array")

    config = config or PreprocessConfig()

    if image.ndim == 2:
        working = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.ndim == 3 and image.shape[2] == 4:
        working = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    elif image.ndim == 3 and image.shape[2] == 3:
        working = image.copy()
    else:
        raise ValueError("image must be grayscale, BGR, or BGRA")

    original_height, original_width = working.shape[:2]

    if config.target_width > 0 and original_width > config.target_width:
        scale = config.target_width / original_width
        target_height = max(1, int(round(original_height * scale)))
        working = cv2.resize(
            working,
            (config.target_width, target_height),
            interpolation=cv2.INTER_AREA,
        )

    kernel = config.gaussian_kernel
    if kernel < 1 or kernel % 2 == 0:
        raise ValueError("gaussian_kernel must be a positive odd integer")

    if kernel > 1:
        working = cv2.GaussianBlur(working, (kernel, kernel), 0)

    lab = cv2.cvtColor(working, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(
        clipLimit=config.clahe_clip_limit,
        tileGridSize=config.clahe_grid_size,
    )
    l_channel = clahe.apply(l_channel)

    processed = cv2.cvtColor(
        cv2.merge((l_channel, a_channel, b_channel)),
        cv2.COLOR_LAB2BGR,
    )

    gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))

    quality_reasons: list[str] = []
    if blur_score < config.min_blur_score:
        quality_reasons.append("too_blurry")
    if brightness < config.min_brightness:
        quality_reasons.append("too_dark")
    if brightness > config.max_brightness:
        quality_reasons.append("too_bright")
    if contrast < config.min_contrast:
        quality_reasons.append("low_contrast")

    return PreprocessedFrame(
        image=processed,
        original_width=original_width,
        original_height=original_height,
        processed_width=int(processed.shape[1]),
        processed_height=int(processed.shape[0]),
        blur_score=round(blur_score, 3),
        brightness=round(brightness, 3),
        contrast=round(contrast, 3),
        usable_for_ai=not quality_reasons,
        quality_reasons=tuple(quality_reasons),
    )


def quality_summary(result: PreprocessedFrame) -> dict[str, Any]:
    return {
        "original_size": {
            "width": result.original_width,
            "height": result.original_height,
        },
        "processed_size": {
            "width": result.processed_width,
            "height": result.processed_height,
        },
        "blur_score": result.blur_score,
        "brightness": result.brightness,
        "contrast": result.contrast,
        "usable_for_ai": result.usable_for_ai,
        "quality_reasons": list(result.quality_reasons),
    }
