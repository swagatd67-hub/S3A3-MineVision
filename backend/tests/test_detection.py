import cv2
import numpy as np

from backend.app.services.video.detection import (
    Detection,
    DetectionResult,
    NullDetector,
    analyze_image,
    filter_detections,
    result_to_dict,
)


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
