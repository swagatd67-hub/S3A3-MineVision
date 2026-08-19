import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch

from backend.app.services.video.detection import (
    Detection,
    DetectionResult,
    NullDetector,
    analyze_frame_with_sewer_ml,
    analyze_image,
    analyze_image_with_sewer_ml,
    filter_detections,
    result_to_dict,
)
from backend.app.services.video.sewer_classifier import (
    SewerMLInferenceEngine,
    SewerMLResult,
)
from backend.app.services.video.sewer_dataset import DEFECT_CLASSES
from backend.app.services.video.sewer_model import SewerDefectClassifier


def test_null_detector_is_deterministic():
    detector = NullDetector()
    image = np.zeros((120, 160, 3), dtype=np.uint8)

    result = detector.predict(image)

    assert result.image_width == 160
    assert result.image_height == 120
    assert result.detections == []
    assert result.model == "null"


def test_detection_serialization():
    detection = Detection(
        label="person",
        confidence=0.87654,
        x1=10.0,
        y1=20.0,
        x2=50.0,
        y2=80.0,
    )

    result = DetectionResult(
        image_width=100,
        image_height=200,
        detections=[detection],
        model="test",
        inference_ms=12.5,
    )

    payload = result_to_dict(result)

    assert payload["detections"][0]["label"] == "person"
    assert payload["detections"][0]["confidence"] == 0.8765
    assert payload["detections"][0]["box"]["x1"] == 10.0


def test_filter_detections():
    detections = [
        Detection("a", 0.9, 0, 0, 1, 1),
        Detection("b", 0.2, 0, 0, 1, 1),
    ]

    filtered = filter_detections(
        detections,
        min_confidence=0.5,
    )

    assert [item.label for item in filtered] == ["a"]


def test_analyze_image_reads_real_file(tmp_path):
    image_path = tmp_path / "sample.png"

    cv2.imwrite(
        str(image_path),
        np.full(
            (80, 100, 3),
            128,
            dtype=np.uint8,
        ),
    )

    result = analyze_image(
        image_path,
        NullDetector(),
    )

    assert result.image_width == 100
    assert result.image_height == 80
    assert result.detections == []


@pytest.fixture
def dummy_sewer_engine(tmp_path: Path) -> SewerMLInferenceEngine:
    model = SewerDefectClassifier(num_classes=17, pretrained=False)
    checkpoint_path = tmp_path / "dummy_checkpoint.pt"
    thresholds_path = tmp_path / "dummy_thresholds.json"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "classes": DEFECT_CLASSES,
        },
        checkpoint_path,
    )

    thresholds_data = {cls_code: 0.5 for cls_code in DEFECT_CLASSES}
    thresholds_path.write_text(json.dumps(thresholds_data), encoding="utf-8")

    return SewerMLInferenceEngine(
        checkpoint_path=checkpoint_path,
        thresholds_path=thresholds_path,
        device="cpu",
    )


def test_analyze_frame_with_sewer_ml_synthetic_frame(
    dummy_sewer_engine: SewerMLInferenceEngine,
) -> None:
    synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = analyze_frame_with_sewer_ml(synthetic_frame, engine=dummy_sewer_engine)

    assert isinstance(result, SewerMLResult)
    assert len(result.decisions) == 17
    assert result.inference_ms > 0
    assert result.model_version == "sewer-ml-e009"


def test_analyze_frame_with_sewer_ml_engine_injection(
    dummy_sewer_engine: SewerMLInferenceEngine,
) -> None:
    frame = np.full((224, 224, 3), fill_value=200, dtype=np.uint8)
    result = analyze_frame_with_sewer_ml(frame, engine=dummy_sewer_engine)

    assert len(result.decisions) == 17
    for decision in result.decisions:
        assert 0.0 <= decision.probability <= 1.0


def test_analyze_frame_with_sewer_ml_invalid_frame_shape(
    dummy_sewer_engine: SewerMLInferenceEngine,
) -> None:
    with pytest.raises(ValueError, match="non-empty numpy array"):
        analyze_frame_with_sewer_ml(np.array([]), engine=dummy_sewer_engine)

    with pytest.raises(ValueError, match="3-channel BGR image"):
        analyze_frame_with_sewer_ml(
            np.zeros((100, 100), dtype=np.uint8), engine=dummy_sewer_engine
        )


def test_analyze_image_with_sewer_ml_from_file(
    dummy_sewer_engine: SewerMLInferenceEngine,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "sewer_test.png"
    cv2.imwrite(
        str(image_path),
        np.full((120, 160, 3), fill_value=100, dtype=np.uint8),
    )

    result = analyze_image_with_sewer_ml(image_path, engine=dummy_sewer_engine)
    assert isinstance(result, SewerMLResult)
    assert len(result.decisions) == 17


def test_sewer_ml_adapter_does_not_invoke_yolo_or_mutate_events(
    dummy_sewer_engine: SewerMLInferenceEngine,
) -> None:
    null_detector = NullDetector()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    yolo_result = null_detector.predict(frame)
    sewer_result = analyze_frame_with_sewer_ml(frame, engine=dummy_sewer_engine)

    assert yolo_result.model == "null"
    assert yolo_result.detections == []

    assert sewer_result.model_version == "sewer-ml-e009"
    assert len(sewer_result.decisions) == 17
