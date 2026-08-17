from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from backend.app.services.video.defects import (
    DetectionDisposition,
    DefectClass,
    DefectDetection,
    DetectionEvent,
    filter_defect_candidates,
    validate_confidence,
)


@dataclass(frozen=True)
class RawDetection:
    """Model-agnostic detection emitted by a vision detector."""

    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


# Baseline label mapping. A custom model can later emit these labels directly.
LABEL_TO_DEFECT: dict[str, DefectClass] = {
    "blockage": DefectClass.BLOCKAGE,
    "debris": DefectClass.DEBRIS,
    "crack": DefectClass.CRACK,
    "corrosion": DefectClass.CORROSION,
    "sediment": DefectClass.SEDIMENT,
    "structural_damage": DefectClass.STRUCTURAL_DAMAGE,
    "unknown": DefectClass.UNKNOWN,
}


def map_label_to_defect(label: str) -> DefectClass:
    normalized = label.strip().lower().replace(" ", "_")
    return LABEL_TO_DEFECT.get(normalized, DefectClass.UNKNOWN)


def raw_to_defect(
    raw: RawDetection,
    *,
    disposition: DetectionDisposition = DetectionDisposition.CANDIDATE,
) -> DefectDetection:
    validate_confidence(raw.confidence)

    return DefectDetection(
        defect_class=map_label_to_defect(raw.label),
        confidence=raw.confidence,
        x1=raw.x1,
        y1=raw.y1,
        x2=raw.x2,
        y2=raw.y2,
        disposition=disposition,
    )


def build_detection_events(
    raw_detections: Sequence[RawDetection] | Iterable[RawDetection],
    *,
    mission_id: str,
    frame_index: int,
    timestamp: str,
    distance_m: float,
    source: str,
    model: str,
    min_confidence: float = 0.5,
    preprocessing_usable: bool = True,
) -> list[DetectionEvent]:
    defects = [
        raw_to_defect(item)
        for item in raw_detections
    ]

    candidates = filter_defect_candidates(
        defects,
        min_confidence=min_confidence,
    )

    return [
        DetectionEvent(
            mission_id=mission_id,
            frame_index=frame_index,
            timestamp=timestamp,
            distance_m=distance_m,
            source=source,
            detection=item,
            model=model,
            preprocessing_usable=preprocessing_usable,
        )
        for item in candidates
    ]


def raw_detections_from_result(
    labels: Sequence[str],
    confidences: Sequence[float],
    boxes: Sequence[tuple[float, float, float, float]],
) -> list[RawDetection]:
    if not (
        len(labels) == len(confidences) == len(boxes)
    ):
        raise ValueError("labels, confidences and boxes must have equal lengths")

    return [
        RawDetection(
            label=label,
            confidence=confidence,
            x1=box[0],
            y1=box[1],
            x2=box[2],
            y2=box[3],
        )
        for label, confidence, box in zip(
            labels,
            confidences,
            boxes,
        )
    ]
