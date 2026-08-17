from backend.app.services.video.defects import DefectClass
from backend.app.services.video.detection_events import (
    RawDetection,
    build_detection_events,
    map_label_to_defect,
    raw_detections_from_result,
)


def test_maps_known_labels():
    assert map_label_to_defect("blockage") == DefectClass.BLOCKAGE
    assert map_label_to_defect("Structural Damage") == DefectClass.STRUCTURAL_DAMAGE


def test_unknown_labels_are_safe():
    assert map_label_to_defect("something_else") == DefectClass.UNKNOWN


def test_builds_distance_linked_detection_event():
    events = build_detection_events(
        [
            RawDetection(
                label="blockage",
                confidence=0.91,
                x1=10,
                y1=20,
                x2=80,
                y2=100,
            )
        ],
        mission_id="M-001",
        frame_index=42,
        timestamp="2026-08-17T16:00:00+00:00",
        distance_m=18.74,
        source="webcam",
        model="test-model",
    )

    assert len(events) == 1

    event = events[0]
    assert event.mission_id == "M-001"
    assert event.frame_index == 42
    assert event.distance_m == 18.74
    assert event.detection.defect_class == DefectClass.BLOCKAGE
    assert event.detection.confidence == 0.91
    assert event.detection.disposition.value == "candidate"


def test_confidence_filter_removes_weak_predictions():
    events = build_detection_events(
        [
            RawDetection("crack", 0.49, 0, 0, 1, 1),
            RawDetection("debris", 0.72, 0, 0, 1, 1),
        ],
        mission_id="M-001",
        frame_index=1,
        timestamp="2026-08-17T16:00:00+00:00",
        distance_m=2.0,
        source="webcam",
        model="test-model",
        min_confidence=0.5,
    )

    assert len(events) == 1
    assert events[0].detection.defect_class == DefectClass.DEBRIS


def test_unusable_preprocessing_is_preserved():
    events = build_detection_events(
        [RawDetection("sediment", 0.8, 0, 0, 1, 1)],
        mission_id="M-001",
        frame_index=5,
        timestamp="2026-08-17T16:00:00+00:00",
        distance_m=4.25,
        source="webcam",
        model="test-model",
        preprocessing_usable=False,
    )

    assert events[0].preprocessing_usable is False


def test_raw_result_builder():
    result = raw_detections_from_result(
        labels=["blockage", "crack"],
        confidences=[0.8, 0.6],
        boxes=[(0, 1, 2, 3), (4, 5, 6, 7)],
    )

    assert len(result) == 2
    assert result[0].label == "blockage"
    assert result[1].x2 == 6
