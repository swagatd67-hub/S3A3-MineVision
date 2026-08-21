"""Unit Tests for Inspection Observation Fusion Service."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.services.inspection import (
    BoundingBox,
    DistanceConflictError,
    FusedInspectionObservation,
    InspectionFrameMetadata,
    InvalidPerceptionInputError,
    RawPerceptionItem,
    fuse_observations,
)
from backend.app.services.video.detection import Detection, DetectionResult
from backend.app.services.video.sewer_classifier import ClassDecision, SewerMLResult
from robot.localization.models import LocalizationQuality, RobotPose


def test_yolo_detection_pose_fusion() -> None:
    detection_res = DetectionResult(
        image_width=1920,
        image_height=1080,
        detections=[
            Detection(label="crack", confidence=0.85, x1=100.0, y1=150.0, x2=300.0, y2=400.0)
        ],
        model="yolo11n.pt",
        inference_ms=12.5,
    )
    meta = InspectionFrameMetadata(
        mission_id="MIS-001",
        frame_index=10,
        timestamp="2026-08-21T12:00:00Z",
        distance_m=15.5,
    )
    pose = RobotPose(
        timestamp=datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc),
        distance_m=15.5,
        x=15.5,
        y=0.0,
        heading_rad=0.05,
        heading_deg=2.86,
        quality=LocalizationQuality.TRACKING,
        source="odometry+imu",
    )

    fused = fuse_observations(detection_res, meta, pose)

    assert len(fused) == 1
    obs = fused[0]
    assert isinstance(obs, FusedInspectionObservation)
    assert obs.mission_id == "MIS-001"
    assert obs.frame_index == 10
    assert obs.class_code == "crack"
    assert obs.confidence == 0.85
    assert obs.distance_m == 15.5
    assert obs.localization_quality == "TRACKING"
    assert obs.robot_pose == pose
    assert obs.model_name == "yolo11n.pt"
    assert obs.source_type == "yolo"
    assert isinstance(obs.box, BoundingBox)
    assert obs.box.x1 == 100.0
    assert obs.box.y2 == 400.0


def test_sewer_ml_classification_pose_fusion() -> None:
    sewer_res = SewerMLResult(
        decisions=[
            ClassDecision(class_code="RO", probability=0.92, threshold=0.5, detected=True),
            ClassDecision(class_code="IS", probability=0.12, threshold=0.5, detected=False),
            ClassDecision(class_code="IN", probability=0.78, threshold=0.4, detected=True),
        ],
        detected_classes=["RO", "IN"],
        inference_ms=35.0,
        model_version="sewer-ml-e009",
    )
    meta = InspectionFrameMetadata(
        mission_id="MIS-002",
        frame_index=42,
        timestamp="2026-08-21T12:05:00Z",
        distance_m=28.0,
    )
    pose = RobotPose(
        timestamp=datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc),
        distance_m=28.0,
        x=28.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )

    fused = fuse_observations(sewer_res, meta, pose)

    # Only 2 detected classes ("RO" and "IN")
    assert len(fused) == 2
    ro_obs = fused[0]
    in_obs = fused[1]

    assert ro_obs.class_code == "RO"
    assert ro_obs.confidence == 0.92
    assert ro_obs.threshold == 0.5
    assert ro_obs.box is None  # No bounding box for multi-label classifier!
    assert ro_obs.source_type == "sewer-ml"

    assert in_obs.class_code == "IN"
    assert in_obs.confidence == 0.78
    assert in_obs.threshold == 0.4
    assert in_obs.box is None


def test_missing_localization_unavailable() -> None:
    raw_item = RawPerceptionItem(class_code="debris", confidence=0.7, model_name="yolo")
    meta = InspectionFrameMetadata(
        mission_id="MIS-003",
        frame_index=5,
        timestamp="2026-08-21T10:00:00Z",
        distance_m=12.0,
    )

    fused = fuse_observations(raw_item, meta, robot_pose=None)
    assert len(fused) == 1
    obs = fused[0]

    assert obs.robot_pose is None
    assert obs.localization_quality == "UNAVAILABLE"
    assert obs.distance_m == 12.0


def test_degraded_and_invalid_localization_quality() -> None:
    raw_item = RawPerceptionItem(class_code="crack", confidence=0.8, model_name="yolo")
    meta = InspectionFrameMetadata(mission_id="MIS-004", frame_index=1, distance_m=1.0)

    # Degraded pose
    degraded_pose = RobotPose(
        timestamp=None,
        distance_m=1.0,
        x=1.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.DEGRADED,
    )
    fused_deg = fuse_observations(raw_item, meta, degraded_pose)
    assert fused_deg[0].localization_quality == "DEGRADED"

    # Invalid pose
    invalid_pose = RobotPose(
        timestamp=None,
        distance_m=1.0,
        x=1.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.INVALID,
    )
    fused_inv = fuse_observations(raw_item, meta, invalid_pose)
    assert fused_inv[0].localization_quality == "INVALID"


def test_missing_timestamp_handling() -> None:
    raw_item = RawPerceptionItem(class_code="corrosion", confidence=0.9, model_name="yolo")
    meta = InspectionFrameMetadata(
        mission_id="MIS-005", frame_index=1, timestamp=None, distance_m=5.0
    )

    # Fallback to pose timestamp if available
    pose_ts = datetime(2026, 8, 21, 14, 0, 0, tzinfo=timezone.utc)
    pose = RobotPose(
        timestamp=pose_ts,
        distance_m=5.0,
        x=5.0,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )
    fused = fuse_observations(raw_item, meta, pose)
    assert fused[0].timestamp == pose_ts

    # If both missing
    fused_none = fuse_observations(raw_item, meta, robot_pose=None)
    assert fused_none[0].timestamp is None
    assert fused_none[0].timestamp_iso is None


def test_conflicting_distance_handling() -> None:
    raw_item = RawPerceptionItem(class_code="crack", confidence=0.8, model_name="yolo")
    meta = InspectionFrameMetadata(
        mission_id="MIS-006", frame_index=2, distance_m=10.0
    )
    pose = RobotPose(
        timestamp=None,
        distance_m=11.2,  # 1.2m difference from frame distance
        x=11.2,
        y=0.0,
        heading_rad=0.0,
        heading_deg=0.0,
        quality=LocalizationQuality.TRACKING,
    )

    # Frame preferred (default)
    fused_frame = fuse_observations(raw_item, meta, pose, distance_policy="FRAME_PREFERRED")
    assert fused_frame[0].distance_m == 10.0
    assert fused_frame[0].frame_distance_m == 10.0
    assert fused_frame[0].pose_distance_m == 11.2
    assert pytest.approx(fused_frame[0].distance_conflict_m, rel=1e-3) == 1.2

    # Pose preferred
    fused_pose = fuse_observations(raw_item, meta, pose, distance_policy="POSE_PREFERRED")
    assert fused_pose[0].distance_m == 11.2

    # Strict policy raises DistanceConflictError if diff > threshold (default 0.5m)
    with pytest.raises(DistanceConflictError, match="Distance conflict"):
        fuse_observations(raw_item, meta, pose, distance_policy="STRICT")


def test_deterministic_observation_id() -> None:
    raw_item = RawPerceptionItem(
        class_code="crack",
        confidence=0.85,
        model_name="yolo11n.pt",
        box=BoundingBox(x1=10.0, y1=20.0, x2=30.0, y2=40.0),
    )
    meta = InspectionFrameMetadata(mission_id="MIS-007", frame_index=1, distance_m=1.0)

    fused1 = fuse_observations(raw_item, meta)[0]
    fused2 = fuse_observations(raw_item, meta)[0]

    assert fused1.observation_id == fused2.observation_id
    assert fused1.observation_id.startswith("obs-")


def test_multiple_models_and_defects_in_one_frame() -> None:
    detection_res = DetectionResult(
        image_width=1280,
        image_height=720,
        detections=[
            Detection(label="crack", confidence=0.8, x1=10, y1=10, x2=50, y2=50)
        ],
        model="yolo11n.pt",
    )
    sewer_res = SewerMLResult(
        decisions=[
            ClassDecision(class_code="RO", probability=0.9, threshold=0.5, detected=True)
        ],
        detected_classes=["RO"],
        inference_ms=10.0,
        model_version="e009",
    )

    meta = InspectionFrameMetadata(
        mission_id="MIS-MULTI", frame_index=99, distance_m=50.0
    )

    fused_yolo = fuse_observations(detection_res, meta)
    fused_sewer = fuse_observations(sewer_res, meta)

    assert len(fused_yolo) == 1
    assert fused_yolo[0].model_name == "yolo11n.pt"
    assert fused_yolo[0].box is not None

    assert len(fused_sewer) == 1
    assert fused_sewer[0].model_name == "sewer-ml-e009"
    assert fused_sewer[0].box is None


def test_input_objects_are_not_mutated() -> None:
    det = Detection(label="crack", confidence=0.8, x1=10, y1=10, x2=50, y2=50)
    detection_res = DetectionResult(
        image_width=1280, image_height=720, detections=[det], model="yolo"
    )
    meta = InspectionFrameMetadata(
        mission_id="MIS-MUT", frame_index=1, distance_m=2.0
    )

    fuse_observations(detection_res, meta)

    assert detection_res.detections[0] == det
    assert meta.mission_id == "MIS-MUT"


def test_unsupported_perception_input_type() -> None:
    meta = InspectionFrameMetadata(mission_id="MIS-ERR", frame_index=1)
    with pytest.raises(InvalidPerceptionInputError, match="Unsupported perception input"):
        fuse_observations(object(), meta)
