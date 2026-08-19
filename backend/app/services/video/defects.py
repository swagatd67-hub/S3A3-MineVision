from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DefectClass(StrEnum):
    BLOCKAGE = "blockage"
    DEBRIS = "debris"
    CRACK = "crack"
    CORROSION = "corrosion"
    SEDIMENT = "sediment"
    STRUCTURAL_DAMAGE = "structural_damage"
    UNKNOWN = "unknown"


class DetectionDisposition(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


@dataclass(frozen=True)
class DefectDetection:
    defect_class: DefectClass
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    disposition: DetectionDisposition = DetectionDisposition.CANDIDATE

    def to_dict(self) -> dict[str, Any]:
        return {
            "defect_class": self.defect_class.value,
            "confidence": round(self.confidence, 4),
            "box": {
                "x1": self.x1,
                "y1": self.y1,
                "x2": self.x2,
                "y2": self.y2,
            },
            "disposition": self.disposition.value,
        }


@dataclass(frozen=True)
class DetectionEvent:
    mission_id: str
    frame_index: int
    timestamp: str
    distance_m: float
    source: str
    detection: DefectDetection
    model: str
    preprocessing_usable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "visual_defect_candidate",
            "mission_id": self.mission_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "distance_m": self.distance_m,
            "source": self.source,
            "model": self.model,
            "preprocessing_usable": self.preprocessing_usable,
            "detection": self.detection.to_dict(),
        }


SUPPORTED_DEFECT_CLASSES: tuple[DefectClass, ...] = (
    DefectClass.BLOCKAGE,
    DefectClass.DEBRIS,
    DefectClass.CRACK,
    DefectClass.CORROSION,
    DefectClass.SEDIMENT,
    DefectClass.STRUCTURAL_DAMAGE,
)


def validate_confidence(confidence: float) -> float:
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return confidence


def filter_defect_candidates(
    detections: Sequence[DefectDetection],
    *,
    min_confidence: float = 0.5,
) -> list[DefectDetection]:
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1")

    return [
        detection
        for detection in detections
        if detection.confidence >= min_confidence
        and detection.disposition != DetectionDisposition.REJECTED
    ]
