import pytest

from backend.app.services.video.defects import (
    DefectClass,
    DefectDetection,
    DetectionDisposition,
    filter_defect_candidates,
    validate_confidence,
)


def test_supported_defect_values_are_stable():
    assert DefectClass.BLOCKAGE.value == "blockage"
    assert DefectClass.DEBRIS.value == "debris"
    assert DefectClass.CRACK.value == "crack"
    assert DefectClass.CORROSION.value == "corrosion"
    assert DefectClass.SEDIMENT.value == "sediment"
    assert DefectClass.STRUCTURAL_DAMAGE.value == "structural_damage"


def test_defect_detection_serialization():
    detection = DefectDetection(
        defect_class=DefectClass.BLOCKAGE,
        confidence=0.91,
        x1=10,
        y1=20,
        x2=80,
        y2=100,
    )

    payload = detection.to_dict()

    assert payload["defect_class"] == "blockage"
    assert payload["confidence"] == 0.91
    assert payload["disposition"] == "candidate"


def test_filter_candidates_by_confidence():
    detections = [
        DefectDetection(DefectClass.BLOCKAGE, 0.9, 0, 0, 1, 1),
        DefectDetection(DefectClass.CRACK, 0.3, 0, 0, 1, 1),
    ]

    result = filter_defect_candidates(
        detections,
        min_confidence=0.5,
    )

    assert len(result) == 1
    assert result[0].defect_class == DefectClass.BLOCKAGE


def test_rejected_detection_is_not_candidate():
    detection = DefectDetection(
        defect_class=DefectClass.DEBRIS,
        confidence=0.99,
        x1=0,
        y1=0,
        x2=1,
        y2=1,
        disposition=DetectionDisposition.REJECTED,
    )

    assert filter_defect_candidates([detection]) == []


def test_confidence_validation():
    assert validate_confidence(0.0) == 0.0
    assert validate_confidence(1.0) == 1.0

    with pytest.raises(ValueError):
        validate_confidence(1.1)

    with pytest.raises(ValueError):
        validate_confidence(-0.1)
