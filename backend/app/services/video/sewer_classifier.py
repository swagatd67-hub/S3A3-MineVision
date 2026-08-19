from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import transforms

from backend.app.services.video.sewer_dataset import DEFECT_CLASSES
from backend.app.services.video.sewer_model import (
    SewerDefectClassifier,
    load_sewer_classifier,
)

DEFAULT_CHECKPOINT_PATH = Path("experiments/sewer/E009/best.pt")
DEFAULT_THRESHOLDS_PATH = Path("experiments/sewer/E009/thresholds.json")
DEFAULT_MODEL_VERSION = "sewer-ml-e009"


@dataclass(frozen=True)
class ClassDecision:
    """Individual class prediction decision with calibrated threshold."""

    class_code: str
    probability: float
    threshold: float
    detected: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_code": self.class_code,
            "probability": round(self.probability, 4),
            "threshold": round(self.threshold, 4),
            "detected": self.detected,
        }


@dataclass(frozen=True)
class SewerMLResult:
    """Multi-label classification result for a frame."""

    decisions: list[ClassDecision]
    detected_classes: list[str]
    inference_ms: float
    model_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "inference_ms": round(self.inference_ms, 2),
            "detected_classes": self.detected_classes,
            "decisions": [d.to_dict() for d in self.decisions],
        }


class SewerMLInferenceEngine:
    """Production multi-label defect classifier engine using Sewer-ML model."""

    def __init__(
        self,
        checkpoint_path: str | Path = DEFAULT_CHECKPOINT_PATH,
        thresholds_path: str | Path = DEFAULT_THRESHOLDS_PATH,
        device: str | torch.device | None = None,
        model_version: str = DEFAULT_MODEL_VERSION,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.thresholds_path = Path(thresholds_path)
        self.model_version = model_version

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        elif isinstance(device, str):
            self.device = torch.device(device)
        else:
            self.device = device

        self.model: SewerDefectClassifier = load_sewer_classifier(
            self.checkpoint_path,
            device=self.device,
        )

        self.thresholds = self._load_thresholds(self.thresholds_path)

        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.485, 0.456, 0.406),
                    std=(0.229, 0.224, 0.225),
                ),
            ]
        )

    def _load_thresholds(self, path: Path) -> dict[str, float]:
        if not path.exists():
            raise FileNotFoundError(f"Thresholds file not found: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(
                f"Failed to parse thresholds JSON from {path}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise TypeError(f"Invalid thresholds format in {path}: expected dict")

        thresholds: dict[str, float] = {}
        for cls in DEFECT_CLASSES:
            val = data.get(cls, 0.5)
            try:
                thresholds[cls] = float(val)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Invalid threshold value for class {cls} in {path}"
                ) from exc

        return thresholds

    def predict(self, image: np.ndarray) -> SewerMLResult:
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("image must be a non-empty numpy array")

        if len(image.shape) != 3 or image.shape[2] != 3:
            raise ValueError("image must be a 3-channel BGR image")

        start_time = time.perf_counter()

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)

        image_tensor = self.transform(pil_image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(image_tensor)
            probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()

        inference_ms = (time.perf_counter() - start_time) * 1000.0

        decisions: list[ClassDecision] = []
        detected_classes: list[str] = []

        for idx, cls_code in enumerate(DEFECT_CLASSES):
            prob = float(probs[idx])
            thresh = self.thresholds.get(cls_code, 0.5)
            is_detected = prob >= thresh

            decisions.append(
                ClassDecision(
                    class_code=cls_code,
                    probability=prob,
                    threshold=thresh,
                    detected=is_detected,
                )
            )

            if is_detected:
                detected_classes.append(cls_code)

        return SewerMLResult(
            decisions=decisions,
            detected_classes=detected_classes,
            inference_ms=inference_ms,
            model_version=self.model_version,
        )
