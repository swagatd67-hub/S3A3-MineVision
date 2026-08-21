"""Comprehensive Unit Tests for Pipe Inspection Mapping Domain."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.services.inspection import (
    BoundingBox,
    InspectionFrameMetadata,
    RawPerceptionItem,
    fuse_observations,
)
from backend.app.services.video.detection import Detection, DetectionResult
from backend.app.services.video.sewer_classifier import ClassDecision, SewerMLResult
from mapping import (
    MapObservation,
    MixedMissionError,
    PipeInspectionMap,
    build_inspection_map,
    build_inspection_maps_by_mission,
)
from robot.localization import LocalizationQuality, RobotLocalizer, RobotPose
from robot.telemetry import parse_telemetry
from robot.transport.simulator import SimulatorTransport


def test_empty_map_generation() -> None:
    inspection_map = build_inspection_map([], mission_id="MIS-EMPTY")

    assert isinstance(inspection_map, PipeInspectionMap)
    assert inspection_map.mission_id == "MIS-EMPTY"
    assert inspection_map.observation_count == 0
    assert inspection_map.observations == ()
    assert inspection_map.total_inspected_distance_m == 0.0
    assert inspection_map.start_distance_m is None
    assert inspection_map.end_distance_m is None


def test_single_and_multiple_observations_map() -> None:
    raw_item = RawPerceptionItem(class_code="crack", confidence=0.85, model_name="yolo")
    meta = InspectionFrameMetadata(
        mission_id="MIS-100", frame_index=1, timestamp="2026-08-21T10:00:00Z", distance_m=5.0
    )
    pose = RobotPose(
        timestamp=datetime(2026, 8, 21, 10, 0, 0, tzinfo=timezone.utc),
        distance_m=5.0,
        x=5.0,
        y=0.0,
        heading_rad=0.1,
        heading_deg=5.73,
        quality=LocalizationQuality.TRACKING,
    )
    fused = fuse_observations(raw_item, meta, pose)

    inspection_map = build_inspection_map(fused)

    assert inspection_map.mission_id == "MIS-100"
    assert inspection_map.observation_count == 1
    assert inspection_map.start_distance_m == 5.0
    assert inspection_map.end_distance_m == 5.0
    assert inspection_map.total_inspected_distance_m == 0.0

    obs = inspection_map.observations[0]
    assert isinstance(obs, MapObservation)
    assert obs.distance_m == 5.0
    assert obs.x == 5.0
    assert obs.y == 0.0
    assert obs.heading_deg == 5.73
    assert obs.class_code == "crack"


def test_distance_ordering_and_tiebreakers() -> None:
    meta1 = InspectionFrameMetadata(
        mission_id="MIS-SORT", frame_index=2, timestamp="2026-08-21T10:00:05Z", distance_m=12.0
    )
    meta2 = InspectionFrameMetadata(
        mission_id="MIS-SORT", frame_index=1, timestamp="2026-08-21T10:00:01Z", distance_m=3.0
    )
    meta3 = InspectionFrameMetadata(
        mission_id="MIS-SORT", frame_index=3, timestamp="2026-08-21T10:00:01Z", distance_m=12.0
    )

    fused1 = fuse_observations(RawPerceptionItem("debris", 0.9, "yolo"), meta1)[0]
    fused2 = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo"), meta2)[0]
    fused3 = fuse_observations(RawPerceptionItem("blockage", 0.7, "yolo"), meta3)[0]

    inspection_map = build_inspection_map([fused1, fused2, fused3])

    assert inspection_map.observation_count == 3
    # Ordered primarily by distance_m (3.0, 12.0, 12.0), secondarily by timestamp
    assert inspection_map.observations[0].distance_m == 3.0
    assert inspection_map.observations[0].class_code == "crack"

    assert inspection_map.observations[1].distance_m == 12.0
    assert inspection_map.observations[1].class_code == "blockage"  # timestamp 10:00:01

    assert inspection_map.observations[2].distance_m == 12.0
    assert inspection_map.observations[2].class_code == "debris"    # timestamp 10:00:05

    assert inspection_map.start_distance_m == 3.0
    assert inspection_map.end_distance_m == 12.0
    assert inspection_map.total_inspected_distance_m == 9.0


def test_duplicate_observation_ids_deduplication() -> None:
    raw = RawPerceptionItem("crack", 0.8, "yolo", box=BoundingBox(10, 10, 20, 20))
    meta = InspectionFrameMetadata("MIS-DUP", 1, distance_m=2.0)

    fused1 = fuse_observations(raw, meta)[0]
    fused2 = fuse_observations(raw, meta)[0]  # Exact duplicate

    assert fused1.observation_id == fused2.observation_id

    inspection_map = build_inspection_map([fused1, fused2])
    assert inspection_map.observation_count == 1


def test_same_distance_distinct_observations_preserved() -> None:
    meta = InspectionFrameMetadata("MIS-SAME", 1, distance_m=5.0)

    fused1 = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo1"), meta)[0]
    fused2 = fuse_observations(RawPerceptionItem("corrosion", 0.7, "yolo2"), meta)[0]

    inspection_map = build_inspection_map([fused1, fused2])
    assert inspection_map.observation_count == 2
    assert inspection_map.observations[0].distance_m == 5.0
    assert inspection_map.observations[1].distance_m == 5.0


def test_mixed_mission_ids_behavior() -> None:
    fused1 = fuse_observations(
        RawPerceptionItem("crack", 0.8, "yolo"),
        InspectionFrameMetadata("MIS-A", 1, distance_m=1.0),
    )[0]
    fused2 = fuse_observations(
        RawPerceptionItem("debris", 0.7, "yolo"),
        InspectionFrameMetadata("MIS-B", 1, distance_m=2.0),
    )[0]

    # Without explicit mission_id, raises MixedMissionError
    with pytest.raises(MixedMissionError, match="multiple distinct mission IDs"):
        build_inspection_map([fused1, fused2])

    # With explicit mission_id parameter, filters correctly
    map_a = build_inspection_map([fused1, fused2], mission_id="MIS-A")
    assert map_a.mission_id == "MIS-A"
    assert map_a.observation_count == 1
    assert map_a.observations[0].class_code == "crack"

    # Grouping helper
    grouped_maps = build_inspection_maps_by_mission([fused1, fused2])
    assert "MIS-A" in grouped_maps
    assert "MIS-B" in grouped_maps
    assert grouped_maps["MIS-A"].observation_count == 1
    assert grouped_maps["MIS-B"].observation_count == 1


def test_localization_quality_preservation() -> None:
    meta_deg = InspectionFrameMetadata("MIS-QUAL", 1, distance_m=10.0)
    meta_inv = InspectionFrameMetadata("MIS-QUAL", 2, distance_m=11.0)

    # Degraded quality
    deg_pose = RobotPose(
        timestamp=None, distance_m=10.0, x=10.0, y=0.0, heading_rad=0.0, heading_deg=0.0, quality=LocalizationQuality.DEGRADED
    )
    fused_deg = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo"), meta_deg, deg_pose)[0]

    # Invalid quality
    inv_pose = RobotPose(
        timestamp=None, distance_m=11.0, x=11.0, y=0.0, heading_rad=0.0, heading_deg=0.0, quality=LocalizationQuality.INVALID
    )
    fused_inv = fuse_observations(RawPerceptionItem("corrosion", 0.9, "yolo"), meta_inv, inv_pose)[0]

    inspection_map = build_inspection_map([fused_deg, fused_inv])

    assert inspection_map.observation_count == 2
    assert inspection_map.observations[0].localization_quality == "DEGRADED"
    assert inspection_map.observations[1].localization_quality == "INVALID"


def test_map_spatial_and_class_queries() -> None:
    meta1 = InspectionFrameMetadata("MIS-Q", 1, distance_m=2.0)
    meta2 = InspectionFrameMetadata("MIS-Q", 2, distance_m=5.0)
    meta3 = InspectionFrameMetadata("MIS-Q", 3, distance_m=10.0)

    fused1 = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo"), meta1)[0]
    fused2 = fuse_observations(RawPerceptionItem("debris", 0.7, "yolo"), meta2)[0]
    fused3 = fuse_observations(RawPerceptionItem("crack", 0.9, "yolo"), meta3)[0]

    inspection_map = build_inspection_map([fused1, fused2, fused3])

    # observations_at_distance
    at_5 = inspection_map.observations_at_distance(5.0, tolerance_m=0.1)
    assert len(at_5) == 1
    assert at_5[0].class_code == "debris"

    # observations_between
    between_1_6 = inspection_map.observations_between(1.0, 6.0)
    assert len(between_1_6) == 2
    assert between_1_6[0].distance_m == 2.0
    assert between_1_6[1].distance_m == 5.0

    # defects_by_class
    cracks = inspection_map.defects_by_class("crack")
    assert len(cracks) == 2
    assert cracks[0].distance_m == 2.0
    assert cracks[1].distance_m == 10.0

    # max_distance
    assert inspection_map.max_distance() == 10.0


def test_yolo_and_sewer_ml_geometry_preservation() -> None:
    yolo_res = DetectionResult(
        image_width=1000,
        image_height=800,
        detections=[Detection(label="crack", confidence=0.8, x1=10, y1=20, x2=30, y2=40)],
        model="yolo11n.pt",
    )
    sewer_res = SewerMLResult(
        decisions=[ClassDecision("RO", 0.9, 0.5, True)],
        detected_classes=["RO"],
        inference_ms=15.0,
        model_version="e009",
    )

    meta = InspectionFrameMetadata("MIS-GEOM", 1, distance_m=15.0)

    fused_yolo = fuse_observations(yolo_res, meta)[0]
    fused_sewer = fuse_observations(sewer_res, meta)[0]

    inspection_map = build_inspection_map([fused_yolo, fused_sewer])

    assert inspection_map.observation_count == 2
    yolo_map_obs = next(obs for obs in inspection_map.observations if obs.source_type == "yolo")
    sewer_map_obs = next(obs for obs in inspection_map.observations if obs.source_type == "sewer-ml")

    assert yolo_map_obs.box is not None
    assert yolo_map_obs.box.x1 == 10.0
    assert sewer_map_obs.box is None


def test_end_to_end_simulator_localization_fusion_mapping_pipeline() -> None:
    # 1. Simulator Transport
    sim = SimulatorTransport(robot_id="PV-SIM-E2E", mission_id="MIS-E2E")
    sim.connect()

    localizer = RobotLocalizer()
    fused_observations = []

    # Step simulation 5 times
    for frame_idx in range(1, 6):
        raw_packet = sim.step()
        telemetry = parse_telemetry(raw_packet)
        assert telemetry is not None

        # 2. Localization
        pose = localizer.update(telemetry)

        # Simulated AI perception result for frame
        yolo_res = DetectionResult(
            image_width=1280,
            image_height=720,
            detections=[
                Detection(label="crack", confidence=0.85, x1=100.0, y1=100.0, x2=200.0, y2=200.0)
            ],
            model="yolo11n.pt",
        )

        frame_meta = InspectionFrameMetadata(
            mission_id=telemetry.mission_id or "MIS-E2E",
            frame_index=frame_idx,
            timestamp=telemetry.timestamp,
            distance_m=telemetry.distance_m,
        )

        # 3. Fusion
        fused = fuse_observations(yolo_res, frame_meta, pose)
        fused_observations.extend(fused)

    sim.disconnect()

    # 4. Map Building
    inspection_map = build_inspection_map(fused_observations)

    assert inspection_map.mission_id == "MIS-E2E"
    assert inspection_map.observation_count == 5
    assert inspection_map.start_distance_m is not None
    assert inspection_map.end_distance_m is not None
    assert inspection_map.end_distance_m >= inspection_map.start_distance_m
    assert inspection_map.total_inspected_distance_m >= 0.0

    # Verify query works on final map
    all_cracks = inspection_map.defects_by_class("crack")
    assert len(all_cracks) == 5
    assert all_cracks[0].localization_quality == "TRACKING"
