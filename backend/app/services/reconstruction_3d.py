"""Deterministic 3D Pipe Reconstruction Map Generator Service."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import InspectionObservationRow, Mission
from backend.app.schemas.reconstruction import (
    BoundingBox2D,
    CenterlinePoint,
    Reconstruction3DOutput,
    ReconstructionDefect,
    ReconstructionSection,
)
from backend.app.services.mission.exceptions import MissionNotFoundError


def _hash_seed(text: str) -> int:
    """Generate a stable 32-bit integer seed from string hash."""
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def _derive_clock_angle_and_str(
    obs: InspectionObservationRow,
) -> tuple[float, str]:
    """Derive circumferential angle (0-360 deg) and 12-hour clock string from observation bounding box or hash."""
    box = obs.box
    if isinstance(box, dict):
        u1 = box.get("x1") or box.get("xmin") or 0.5
        u2 = box.get("x2") or box.get("xmax") or 0.5
        u_center = (float(u1) + float(u2)) / 2.0
    elif isinstance(box, list) and len(box) >= 4:
        u_center = (float(box[1]) + float(box[3])) / 2.0
    else:
        # Fallback to deterministic hash angle
        u_center = (_hash_seed(obs.observation_id) % 360) / 360.0

    if u_center > 1.0:
        u_center = u_center / 1920.0  # normalize pixel units if needed

    u_clamped = max(0.0, min(1.0, u_center))
    angle_deg = round(u_clamped * 360.0, 1)

    hour = round(u_clamped * 12.0) % 12
    display_hour = 12 if hour == 0 else hour
    clock_str = f"{display_hour}:00"

    return angle_deg, clock_str


def generate_3d_reconstruction(
    db: Session,
    mission_id: str,
) -> Reconstruction3DOutput:
    """Generate a deterministic, data-driven 3D pipe reconstruction model for a given mission."""
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise MissionNotFoundError(f"Mission '{mission_id}' not found")

    # Fetch real observations for this mission
    obs_rows = db.scalars(
        select(InspectionObservationRow)
        .where(InspectionObservationRow.mission_id == mission_id)
        .order_by(InspectionObservationRow.distance_m.asc())
    ).all()

    # Determine total pipe length
    if obs_rows:
        max_obs_dist = max(r.distance_m or 0.0 for r in obs_rows)
        total_length_m = max(50.0, round(max_obs_dist + 10.0, 1))
    else:
        seed = _hash_seed(mission_id)
        total_length_m = round(40.0 + (seed % 30), 1)

    diameter_mm = 600.0

    # Calculate progress based on mission status & observations
    status_str = mission.status.upper()
    if status_str in ("COMPLETED", "FINISHED"):
        reconstructed_length_m = total_length_m
    elif status_str in ("INSPECTING", "ACTIVE", "RUNNING"):
        if obs_rows:
            max_dist = max(r.distance_m or 0.0 for r in obs_rows)
            reconstructed_length_m = min(total_length_m, round(max_dist + 5.0, 1))
        else:
            reconstructed_length_m = round(total_length_m * 0.65, 1)
    else:
        reconstructed_length_m = round(total_length_m * 0.35, 1)

    progress_pct = round((reconstructed_length_m / total_length_m) * 100.0, 1)

    # Process defect markers
    defects: list[ReconstructionDefect] = []
    if obs_rows:
        for obs in obs_rows:
            angle_deg, clock_str = _derive_clock_angle_and_str(obs)
            conf = float(obs.confidence if obs.confidence is not None else 0.8)
            severity = (
                "CRITICAL" if conf >= 0.9 else ("HIGH" if conf >= 0.75 else "MEDIUM")
            )

            box_obj = None
            if isinstance(obs.box, dict):
                box_obj = obs.box

            defects.append(
                ReconstructionDefect(
                    id=obs.observation_id,
                    class_code=obs.class_code.upper(),
                    distance_m=round(obs.distance_m or 0.0, 2),
                    clock_position=clock_str,
                    clock_angle_deg=angle_deg,
                    severity=severity,
                    confidence=conf,
                    frame_index=obs.frame_index,
                    box=box_obj,
                )
            )
    else:
        # Fallback deterministic demo defect markers for zero-observation missions
        seed = _hash_seed(mission_id)
        d1 = round(total_length_m * 0.25, 1)
        d2 = round(total_length_m * 0.60, 1)
        defects = [
            ReconstructionDefect(
                id=f"{mission_id}-demo-01",
                class_code="CRACK",
                distance_m=d1,
                clock_position="02:00",
                clock_angle_deg=60.0,
                severity="MEDIUM",
                confidence=0.85,
            ),
            ReconstructionDefect(
                id=f"{mission_id}-demo-02",
                class_code="DEPOSIT",
                distance_m=d2,
                clock_position="08:00",
                clock_angle_deg=240.0,
                severity="HIGH",
                confidence=0.92,
            ),
        ]

    # Partition pipe into sections
    section_count = 10
    sec_len = total_length_m / section_count
    sections: list[ReconstructionSection] = []

    for idx in range(section_count):
        s_start = round(idx * sec_len, 2)
        s_end = round((idx + 1) * sec_len, 2)

        sec_defects = [
            d for d in defects if s_start <= d.distance_m <= s_end
        ]

        if s_end <= reconstructed_length_m:
            sec_status = "ANOMALOUS" if len(sec_defects) > 0 else "RECONSTRUCTED"
        elif s_start < reconstructed_length_m:
            sec_status = "ANOMALOUS" if len(sec_defects) > 0 else "RECONSTRUCTED"
        else:
            sec_status = "PENDING"

        sections.append(
            ReconstructionSection(
                section_index=idx,
                start_distance_m=s_start,
                end_distance_m=s_end,
                status=sec_status,
                outer_radius_mm=diameter_mm / 2.0,
                inner_radius_mm=(diameter_mm / 2.0) - 10.0,
                defect_count=len(sec_defects),
            )
        )

    # Generate smooth centerline points along Z
    centerline: list[CenterlinePoint] = []
    num_pts = 20
    for i in range(num_pts + 1):
        z_pos = round((i / num_pts) * total_length_m, 2)
        centerline.append(CenterlinePoint(x=0.0, y=0.0, z=z_pos))

    return Reconstruction3DOutput(
        mission_id=mission_id,
        robot_id=mission.robot_id,
        status=mission.status,
        total_length_m=total_length_m,
        reconstructed_length_m=reconstructed_length_m,
        progress_percent=progress_pct,
        diameter_mm=diameter_mm,
        section_count=section_count,
        sections=sections,
        centerline=centerline,
        defects=defects,
        generated_at=datetime.now(timezone.utc),
        version="v1.0",
    )
