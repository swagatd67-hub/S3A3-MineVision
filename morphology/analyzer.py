"""Service Engine for Pipe Morphology & Geometry Analysis."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from backend.app.services.inspection.models import (
    BoundingBox,
    FusedInspectionObservation,
)
from mapping.models import MapObservation, PipeInspectionMap
from morphology.models import (
    MorphologyCalibration,
    MorphologySummaryReport,
    PipeMorphologyObservation,
)
from robot.telemetry.models import RobotTelemetry


def calculate_deformation(
    observed_diameter_mm: float | None,
    baseline_diameter_mm: float | None,
) -> float | None:
    """Calculate pipe deformation percentage relative to a baseline pipe diameter.

    Formula:
        deformation_percent = ((baseline - observed) / baseline) * 100.0

    Rules:
        - Returns None if observed or baseline is None.
        - Returns None if baseline <= 0.0 or observed <= 0.0.
    """
    if observed_diameter_mm is None or baseline_diameter_mm is None:
        return None

    obs_val = float(observed_diameter_mm)
    base_val = float(baseline_diameter_mm)

    if base_val <= 0.0 or obs_val <= 0.0:
        return None

    delta = base_val - obs_val
    pct = (delta / base_val) * 100.0
    return round(pct, 4)


def analyze_observation(
    fused_obs: FusedInspectionObservation | MapObservation,
    telemetry: RobotTelemetry | None = None,
    calibration: MorphologyCalibration | None = None,
    direct_pipe_measurement_mm: float | None = None,
) -> PipeMorphologyObservation:
    """Analyze a single inspection observation to produce a PipeMorphologyObservation.

    Distinguishes:
        1. robot_body_diameter_mm (from robot telemetry / crawler expansion)
        2. measured_pipe_diameter_mm (from direct physical sensors)
        3. estimated_pipe_diameter_mm (derived from calibrated vision / features)
    """
    obs_id: str = fused_obs.observation_id
    mission_id: str = fused_obs.mission_id
    frame_index: int = fused_obs.frame_index
    timestamp: datetime | None = fused_obs.timestamp
    timestamp_iso: str | None = fused_obs.timestamp_iso
    source: str = fused_obs.source_type

    raw_dist = fused_obs.distance_m
    distance_m: float = float(raw_dist) if raw_dist is not None else 0.0

    # Preserve robot body diameter from telemetry (do NOT confuse with pipe diameter)
    robot_body_diameter_mm: float | None = None
    if telemetry is not None and telemetry.body_diameter_mm is not None:
        robot_body_diameter_mm = float(telemetry.body_diameter_mm)

    # Explicit BoundingBox | None narrowing to avoid NoneType attribute errors
    pixel_span_px: float | None = None
    box: BoundingBox | None = fused_obs.box
    if box is not None:
        pixel_span_px = abs(float(box.x2) - float(box.x1))

    measured_diameter_mm: float | None = None
    estimated_diameter_mm: float | None = None
    effective_diameter_mm: float | None = None
    quality: str = "UNAVAILABLE"
    calib_mode: str = calibration.calibration_mode if calibration is not None else "UNCALIBRATED"

    # Direct physical measurement takes precedence if supplied
    if direct_pipe_measurement_mm is not None:
        direct_val = float(direct_pipe_measurement_mm)
        if direct_val <= 0.0:
            quality = "INVALID"
            source = "direct_sensor"
        else:
            measured_diameter_mm = direct_val
            effective_diameter_mm = direct_val
            quality = "MEASURED"
            source = "direct_sensor"

    # Vision-based calibrated estimation
    elif calibration is not None and calibration.is_calibrated():
        pixel_scale = calibration.pixel_per_mm
        if pixel_span_px is not None and pixel_scale is not None and float(pixel_scale) > 0.0:
            est_mm = pixel_span_px / float(pixel_scale)
            if est_mm <= 0.0:
                quality = "INVALID"
                source = "vision_calibrated"
            else:
                estimated_diameter_mm = est_mm
                effective_diameter_mm = est_mm
                quality = "ESTIMATED"
                source = "vision_calibrated"

    else:
        quality = "UNAVAILABLE"

    baseline_mm: float | None = None
    if calibration is not None and calibration.baseline_pipe_diameter_mm is not None:
        baseline_mm = float(calibration.baseline_pipe_diameter_mm)

    deformation_pct = calculate_deformation(effective_diameter_mm, baseline_mm)

    return PipeMorphologyObservation(
        observation_id=obs_id,
        mission_id=mission_id,
        frame_index=frame_index,
        timestamp=timestamp,
        timestamp_iso=timestamp_iso,
        distance_m=distance_m,
        robot_body_diameter_mm=robot_body_diameter_mm,
        measured_pipe_diameter_mm=measured_diameter_mm,
        estimated_pipe_diameter_mm=estimated_diameter_mm,
        effective_pipe_diameter_mm=effective_diameter_mm,
        baseline_pipe_diameter_mm=baseline_mm,
        deformation_percent=deformation_pct,
        pixel_span_px=pixel_span_px,
        quality=quality,
        source=source,
        calibration_mode=calib_mode,
    )


def analyze_morphology(
    input_data: Sequence[FusedInspectionObservation] | Sequence[MapObservation] | PipeInspectionMap,
    telemetry_records: Sequence[RobotTelemetry] | None = None,
    calibration: MorphologyCalibration | None = None,
) -> MorphologySummaryReport:
    """Analyze a collection of observations or a PipeInspectionMap for pipe morphology features."""

    mission_id: str = "unknown"
    observations_seq: Sequence[FusedInspectionObservation | MapObservation] = ()

    if isinstance(input_data, PipeInspectionMap):
        mission_id = input_data.mission_id
        observations_seq = input_data.observations
    else:
        observations_seq = input_data
        if len(observations_seq) > 0:
            mission_id = observations_seq[0].mission_id

    # Build telemetry lookup map by distance/timestamp if provided
    telemetry_by_dist: dict[float, RobotTelemetry] = {}
    if telemetry_records is not None:
        for telem in telemetry_records:
            if telem.distance_m is not None:
                telemetry_by_dist[round(float(telem.distance_m), 2)] = telem

    morphology_obs_list: list[PipeMorphologyObservation] = []
    for obs in observations_seq:
        matched_telem: RobotTelemetry | None = None
        obs_dist = obs.distance_m
        if obs_dist is not None and len(telemetry_by_dist) > 0:
            matched_telem = telemetry_by_dist.get(round(float(obs_dist), 2))

        morph_obs = analyze_observation(
            fused_obs=obs,
            telemetry=matched_telem,
            calibration=calibration,
        )
        morphology_obs_list.append(morph_obs)

    # Metrics calculation
    total_count: int = len(morphology_obs_list)
    measured_count: int = sum(1 for o in morphology_obs_list if o.quality == "MEASURED")
    estimated_count: int = sum(1 for o in morphology_obs_list if o.quality == "ESTIMATED")
    unavailable_count: int = sum(1 for o in morphology_obs_list if o.quality == "UNAVAILABLE")
    invalid_count: int = sum(1 for o in morphology_obs_list if o.quality == "INVALID")

    valid_diameters: list[float] = [
        o.effective_pipe_diameter_mm
        for o in morphology_obs_list
        if o.effective_pipe_diameter_mm is not None and o.quality != "INVALID"
    ]
    valid_deformations: list[float] = [
        o.deformation_percent
        for o in morphology_obs_list
        if o.deformation_percent is not None
    ]

    min_diam: float | None = min(valid_diameters) if len(valid_diameters) > 0 else None
    max_diam: float | None = max(valid_diameters) if len(valid_diameters) > 0 else None
    mean_diam: float | None = (
        (sum(valid_diameters) / float(len(valid_diameters)))
        if len(valid_diameters) > 0
        else None
    )

    max_def: float | None = max(valid_deformations) if len(valid_deformations) > 0 else None
    mean_def: float | None = (
        (sum(valid_deformations) / float(len(valid_deformations)))
        if len(valid_deformations) > 0
        else None
    )

    return MorphologySummaryReport(
        mission_id=mission_id,
        total_observations=total_count,
        measured_count=measured_count,
        estimated_count=estimated_count,
        unavailable_count=unavailable_count,
        invalid_count=invalid_count,
        min_observed_diameter_mm=min_diam,
        max_observed_diameter_mm=max_diam,
        mean_observed_diameter_mm=mean_diam,
        max_deformation_percent=max_def,
        mean_deformation_percent=mean_def,
        observations=tuple(morphology_obs_list),
    )
