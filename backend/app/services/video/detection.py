from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import cv2
import numpy as np

if TYPE_CHECKING:
    from backend.app.services.video.sewer_classifier import (
        SewerMLInferenceEngine,
        SewerMLResult,
    )


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def box(self) -> dict[str, float]:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }


@dataclass(frozen=True)
class DetectionResult:
    image_width: int
    image_height: int
    detections: list[Detection]
    model: str
    inference_ms: float | None = None


class Detector(Protocol):
    def predict(self, image: np.ndarray) -> DetectionResult: ...


class NullDetector:
    """Deterministic no-op detector for pipeline tests and CI."""

    def __init__(self, model: str = "null") -> None:
        self.model = model

    def predict(self, image: np.ndarray) -> DetectionResult:
        if image is None or image.size == 0:
            raise ValueError("image must be a non-empty numpy array")

        height, width = image.shape[:2]
        return DetectionResult(
            image_width=width,
            image_height=height,
            detections=[],
            model=self.model,
            inference_ms=0.0,
        )


class UltralyticsDetector:
    """Adapter around an Ultralytics YOLO model.

    This is a general-object baseline. A future pipe-defect model can replace
    the weights without changing the rest of the PipeVision pipeline.
    """

    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        confidence_threshold: float = 0.25,
        device: str | None = None,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics is not installed. Install it before using YOLO."
            ) from exc

        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.model = YOLO(model_path)

    def predict(self, image: np.ndarray) -> DetectionResult:
        if image is None or image.size == 0:
            raise ValueError("image must be a non-empty numpy array")

        kwargs: dict[str, Any] = {
            "conf": self.confidence_threshold,
            "verbose": False,
        }
        if self.device:
            kwargs["device"] = self.device

        results = self.model.predict(image, **kwargs)

        height, width = image.shape[:2]
        detections: list[Detection] = []

        if not results:
            return DetectionResult(
                image_width=width,
                image_height=height,
                detections=detections,
                model=self.model_path,
            )

        boxes = results[0].boxes
        names = results[0].names

        if boxes is not None:
            for index in range(len(boxes)):
                coords = boxes.xyxy[index].tolist()
                confidence = float(boxes.conf[index].item())
                class_id = int(boxes.cls[index].item())

                detections.append(
                    Detection(
                        label=str(names[class_id]),
                        confidence=confidence,
                        x1=float(coords[0]),
                        y1=float(coords[1]),
                        x2=float(coords[2]),
                        y2=float(coords[3]),
                    )
                )

        return DetectionResult(
            image_width=width,
            image_height=height,
            detections=detections,
            model=self.model_path,
        )


def load_detector(
    model: str = "null",
    *,
    confidence_threshold: float = 0.25,
) -> Detector:
    if model == "null":
        return NullDetector()

    return UltralyticsDetector(
        model_path=model,
        confidence_threshold=confidence_threshold,
    )


def analyze_image(
    image_path: str | Path,
    detector: Detector,
) -> DetectionResult:
    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(f"Unable to read image: {image_path}")

    return detector.predict(image)


def detection_to_dict(detection: Detection) -> dict[str, Any]:
    return {
        "label": detection.label,
        "confidence": round(detection.confidence, 4),
        "box": detection.box,
    }


def result_to_dict(result: DetectionResult) -> dict[str, Any]:
    return {
        "model": result.model,
        "image_width": result.image_width,
        "image_height": result.image_height,
        "inference_ms": result.inference_ms,
        "detections": [detection_to_dict(item) for item in result.detections],
    }


def filter_detections(
    detections: Sequence[Detection],
    *,
    min_confidence: float = 0.25,
) -> list[Detection]:
    return [item for item in detections if item.confidence >= min_confidence]


def analyze_frame_with_sewer_ml(
    image: np.ndarray,
    engine: SewerMLInferenceEngine | None = None,
) -> SewerMLResult:
    """Run Sewer-ML multi-label classification on an OpenCV BGR frame array."""
    from backend.app.services.video.sewer_classifier import analyze_sewer_frame

    return analyze_sewer_frame(image, engine=engine)


def analyze_image_with_sewer_ml(
    image_path: str | Path,
    engine: SewerMLInferenceEngine | None = None,
) -> SewerMLResult:
    """Read an image file from disk and run Sewer-ML multi-label classification."""
    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(f"Unable to read image: {image_path}")

    return analyze_frame_with_sewer_ml(image, engine=engine)
