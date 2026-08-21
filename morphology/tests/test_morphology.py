"""Comprehensive Unit Tests for Pipe Morphology & Geometry Analysis Layer."""

from __future__ import annotations

import pytest

from backend.app.services.inspection import (
    InspectionFrameMetadata,
    RawPerceptionItem,
    fuse_observations,
)
from backend.app.services.video.detection import Detection, DetectionResult
from mapping import build_inspection_map
from morphology import (
    MorphologyCalibration,
    MorphologySummaryReport,
    PipeMorphologyObservation,
    analyze_morphology,
    analyze_observation,
    calculate_deformation,
)
from robot.localization import RobotLocalizer
from robot.telemetry import RobotTelemetry, parse_telemetry
from robot.transport.simulator import SimulatorTransport


def test_valid_physical_diameter_measurement() -> None:
    fused = fuse_observations(
        RawPerceptionItem("crack", 0.8, "yolo"),
        InspectionFrameMetadata("MIS-PHYS", 1, distance_m=10.0),
    )[0]

    obs = analyze_observation(fused, direct_pipe_measurement_mm=450.0)

    assert isinstance(obs, PipeMorphologyObservation)
    assert obs.quality == "MEASURED"
    assert obs.measured_pipe_diameter_mm == 450.0
    assert obs.effective_pipe_diameter_mm == 450.0
    assert obs.source == "direct_sensor"


def test_robot_body_diameter_preservation_and_distinction() -> None:
    fused = fuse_observations(
        RawPerceptionItem("crack", 0.8, "yolo"),
        InspectionFrameMetadata("MIS-BODY", 1, distance_m=5.0),
    )[0]
    telem = RobotTelemetry(
        robot_id="PV-01",
        mission_id="MIS-BODY",
        distance_m=5.0,
        body_diameter_mm=220.0,
    )

    # Without direct measurement or calibration, pipe diameter is UNAVAILABLE
    obs = analyze_observation(fused, telemetry=telem)

    assert obs.robot_body_diameter_mm == 220.0  # Preserved explicitly from telemetry!
    assert obs.measured_pipe_diameter_mm is None
    assert obs.estimated_pipe_diameter_mm is None
    assert obs.effective_pipe_diameter_mm is None
    assert obs.quality == "UNAVAILABLE"  # NOT confused with pipe diameter!


def test_unavailable_calibration_no_fabricated_conversion() -> None:
    yolo_res = DetectionResult(
        image_width=1000,
        image_height=800,
        detections=[Detection("crack", 0.8, 100.0, 100.0, 300.0, 200.0)],
        model="yolo",
    )
    fused = fuse_observations(
        yolo_res,
        InspectionFrameMetadata("MIS-UNCAL", 1, distance_m=12.0),
    )[0]

    uncalib = MorphologyCalibration(calibration_mode="UNCALIBRATED")
    obs = analyze_observation(fused, calibration=uncalib)

    assert obs.pixel_span_px == 200.0  # Pixel bounding box width preserved
    assert obs.estimated_pipe_diameter_mm is None  # No fake mm conversion!
    assert obs.quality == "UNAVAILABLE"


def test_calibrated_vision_estimation() -> None:
    yolo_res = DetectionResult(
        image_width=1000,
        image_height=800,
        detections=[Detection("crack", 0.8, 100.0, 100.0, 300.0, 200.0)],
        model="yolo",
    )
    fused = fuse_observations(
        yolo_res,
        InspectionFrameMetadata("MIS-CAL", 1, distance_m=12.0),
    )[0]

    # 0.5 pixels per millimeter -> 200 px span = 400 mm estimated diameter
    calib = MorphologyCalibration(
        baseline_pipe_diameter_mm=500.0,
        pixel_per_mm=0.5,
        calibration_mode="CAMERA_CALIBRATED",
    )
    obs = analyze_observation(fused, calibration=calib)

    assert obs.quality == "ESTIMATED"
    assert obs.estimated_pipe_diameter_mm == 400.0
    assert obs.effective_pipe_diameter_mm == 400.0
    assert obs.baseline_pipe_diameter_mm == 500.0
    # deformation_percent = ((500 - 400) / 500) * 100 = 20.0%
    assert obs.deformation_percent == 20.0


def test_invalid_measurement_handling() -> None:
    fused = fuse_observations(
        RawPerceptionItem("crack", 0.8, "yolo"),
        InspectionFrameMetadata("MIS-INV", 1, distance_m=1.0),
    )[0]

    obs = analyze_observation(fused, direct_pipe_measurement_mm=-50.0)

    assert obs.quality == "INVALID"
    assert obs.effective_pipe_diameter_mm is None
    assert obs.deformation_percent is None


def test_calculate_deformation_logic() -> None:
    # Standard deformation: (500 - 450) / 500 * 100 = 10.0%
    assert calculate_deformation(450.0, 500.0) == 10.0

    # Expansion: (500 - 550) / 500 * 100 = -10.0%
    assert calculate_deformation(550.0, 500.0) == -10.0

    # No baseline -> None
    assert calculate_deformation(450.0, None) is None

    # No observed -> None
    assert calculate_deformation(None, 500.0) is None

    # Zero or negative baseline -> None
    assert calculate_deformation(450.0, 0.0) is None
    assert calculate_deformation(450.0, -100.0) is None

    # Zero or negative observed -> None
    assert calculate_deformation(0.0, 500.0) is None
    assert calculate_deformation(-50.0, 500.0) is None


def test_morphology_summary_report_generation() -> None:
    meta1 = InspectionFrameMetadata("MIS-SUM", 1, distance_m=2.0)
    meta2 = InspectionFrameMetadata("MIS-SUM", 2, distance_m=5.0)

    fused1 = fuse_observations(RawPerceptionItem("crack", 0.8, "yolo"), meta1)[0]
    fused2 = fuse_observations(RawPerceptionItem("corrosion", 0.9, "yolo"), meta2)[0]

    inspection_map = build_inspection_map([fused1, fused2])

    calib = MorphologyCalibration(
        baseline_pipe_diameter_mm=500.0,
        pixel_per_mm=0.5,
        calibration_mode="CAMERA_CALIBRATED",
    )

    report = analyze_morphology(inspection_map, calibration=calib)

    assert isinstance(report, MorphologySummaryReport)
    assert report.mission_id == "MIS-SUM"
    assert report.total_observations == 2
    assert report.unavailable_count == 2
    assert report.min_observed_diameter_mm is None


def test_end_to_end_simulator_morphology_pipeline() -> None:
    sim = SimulatorTransport(robot_id="PV-SIM-MORPH", mission_id="MIS-MORPH")
    sim.connect()

    localizer = RobotLocalizer()
    fused_list = []
    telemetry_records = []

    for idx in range(1, 4):
        packet = sim.step()
        telem = parse_telemetry(packet)
        assert telem is not None
        telemetry_records.append(telem)

        pose = localizer.update(telem)

        yolo_res = DetectionResult(
            image_width=1000,
            image_height=800,
            detections=[Detection("crack", 0.85, 100.0, 100.0, 350.0, 250.0)],
            model="yolo",
        )
        meta = InspectionFrameMetadata("MIS-MORPH", idx, telem.timestamp, telem.distance_m)

        fused = fuse_observations(yolo_res, meta, pose)[0]
        fused_list.append(fused)

    sim.disconnect()

    inspection_map = build_inspection_map(fused_list)

    calib = MorphologyCalibration(
        baseline_pipe_diameter_mm=600.0,
        pixel_per_mm=0.5,  # 250 px span -> 500 mm estimated diameter
        calibration_mode="CAMERA_CALIBRATED",
    )

    report = analyze_morphology(
        inspection_map,
        telemetry_records=telemetry_records,
        calibration=calib,
    )

    assert report.mission_id == "MIS-MORPH"
    assert report.total_observations == 3
    assert report.estimated_count == 3
    assert report.mean_observed_diameter_mm == 500.0
    # deformation = ((600 - 500) / 600) * 100 = 16.6667%
    assert pytest.approx(report.mean_deformation_percent, rel=1e-2) == 16.67
    assert report.observations[0].robot_body_diameter_mm is not None
