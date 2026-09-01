from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

import cv2
import numpy as np
from PIL import Image

from backend.app.services.video.sewer_dataset import DEFECT_CLASSES

try:
    import torch
    from torchvision import transforms

    from backend.app.services.video.sewer_model import (
        SewerDefectClassifier,
        load_sewer_classifier,
    )
except ImportError:
    torch = None
    transforms = None
    SewerDefectClassifier = None
    load_sewer_classifier = None

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_PATH = Path("experiments/sewer/E009/best.pt")
DEFAULT_THRESHOLDS_PATH = Path("experiments/sewer/E009/thresholds.json")
DEFAULT_MODEL_VERSION = "sewer-ml-e009"


class SewerMLEngineProtocol(Protocol):
    """Protocol representing any Sewer-ML inference engine (production or null test double)."""

    model_version: str

    def predict(self, image: np.ndarray) -> SewerMLResult:
        ...


_ENGINE_LOCK = Lock()
_SHARED_ENGINE: SewerMLEngineProtocol | None = None


class NullSewerMLEngine:
    """Deterministic no-op Sewer-ML engine for off-hardware testing/CI when model weights are absent."""

    def __init__(self, model_version: str = "sewer-ml-null") -> None:
        self.model_version = model_version

    def predict(self, image: np.ndarray) -> SewerMLResult:
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("image must be a non-empty numpy array")

        decisions = [
            ClassDecision(class_code=cls, probability=0.01, threshold=0.5, detected=False)
            for cls in DEFECT_CLASSES
        ]
        return SewerMLResult(
            decisions=decisions,
            detected_classes=[],
            inference_ms=0.1,
            model_version=self.model_version,
        )


def get_default_checkpoint_path() -> Path:
    env_path = os.getenv("SEWER_CHECKPOINT_PATH")
    return Path(env_path) if env_path else DEFAULT_CHECKPOINT_PATH


def get_default_thresholds_path() -> Path:
    env_path = os.getenv("SEWER_THRESHOLDS_PATH")
    return Path(env_path) if env_path else DEFAULT_THRESHOLDS_PATH


def get_sewer_classifier_engine(
    checkpoint_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
    device: str | torch.device | None = None,
    force_reload: bool = False,
    allow_null_fallback: bool = False,
) -> SewerMLEngineProtocol:
    """Thread-safe singleton getter for SewerMLInferenceEngine.

    By default (allow_null_fallback=False), missing model checkpoints raise FileNotFoundError
    in production. Null engine fallback is only enabled when allow_null_fallback=True or when
    ALLOW_NULL_SEWER_ENGINE environment variable is set to true.
    """
    global _SHARED_ENGINE

    with _ENGINE_LOCK:
        if _SHARED_ENGINE is None or force_reload:
            ckpt_path = (
                Path(checkpoint_path)
                if checkpoint_path is not None
                else get_default_checkpoint_path()
            )
            thresh_path = (
                Path(thresholds_path)
                if thresholds_path is not None
                else get_default_thresholds_path()
            )

            if not ckpt_path.exists():
                is_null_allowed = (
                    allow_null_fallback
                    or os.getenv("ALLOW_NULL_SEWER_ENGINE", "").lower() in ("1", "true", "yes")
                )
                if is_null_allowed:
                    logger.warning(
                        "Sewer-ML checkpoint not found at %s. Falling back to NullSewerMLEngine (explicitly enabled).",
                        ckpt_path,
                    )
                    _SHARED_ENGINE = NullSewerMLEngine()
                else:
                    raise FileNotFoundError(
                        f"Sewer-ML model checkpoint not found at '{ckpt_path}'. Production model loading requires valid weights."
                    )
            else:
                _SHARED_ENGINE = SewerMLInferenceEngine(
                    checkpoint_path=ckpt_path,
                    thresholds_path=thresh_path,
                    device=device,
                )

        assert _SHARED_ENGINE is not None
        return _SHARED_ENGINE


def reset_sewer_classifier_engine() -> None:
    """Reset cached singleton engine (used for testing or reload)."""
    global _SHARED_ENGINE
    with _ENGINE_LOCK:
        _SHARED_ENGINE = None


def analyze_sewer_frame(
    image: np.ndarray,
    engine: SewerMLEngineProtocol | None = None,
) -> SewerMLResult:
    """Service-level function to run Sewer-ML inference on an OpenCV BGR frame."""
    active_engine = engine or get_sewer_classifier_engine()
    return active_engine.predict(image)


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
