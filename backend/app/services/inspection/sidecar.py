"""Sidecar Metadata Parser for Offline Media Ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from robot.localization.models import LocalizationQuality, RobotPose


@dataclass(frozen=True)
class SidecarFrameMetadata:
    """Typed metadata extracted from a JSON sidecar file or global metadata file."""

    timestamp: datetime | None = None
    distance_m: float | None = None
    robot_id: str | None = None
    camera_id: str | None = None
    pose: RobotPose | None = None
    extra: dict[str, Any] | None = None


def parse_sidecar_dict(payload: dict[str, Any]) -> SidecarFrameMetadata:
    """Parse raw sidecar dictionary into typed SidecarFrameMetadata."""
    ts: datetime | None = None
    raw_ts = payload.get("timestamp")
    if isinstance(raw_ts, str) and raw_ts.strip():
        try:
            ts = datetime.fromisoformat(raw_ts)
        except ValueError:
            ts = None

    raw_dist = payload.get("distance_m")
    dist: float | None = float(raw_dist) if raw_dist is not None else None

    robot_id = str(payload["robot_id"]) if payload.get("robot_id") is not None else None
    camera_id = str(payload["camera_id"]) if payload.get("camera_id") is not None else None

    pose: RobotPose | None = None
    raw_pose = payload.get("pose")
    if isinstance(raw_pose, dict):
        import math

        pose_x = raw_pose.get("x")
        pose_dist = raw_pose.get("distance_m")

        effective_dist: float | None = dist
        if effective_dist is None and pose_dist is not None:
            effective_dist = float(pose_dist)
        if effective_dist is None and pose_x is not None:
            effective_dist = float(pose_x)

        effective_x: float | None = float(pose_x) if pose_x is not None else effective_dist

        # Only construct RobotPose when position/distance information is genuinely available
        if effective_dist is not None and effective_x is not None:
            py = float(raw_pose.get("y", 0.0))
            heading_deg = float(raw_pose.get("heading_deg", 0.0))
            raw_rad = raw_pose.get("heading_rad")
            heading_rad = float(raw_rad) if raw_rad is not None else math.radians(heading_deg)
            qual_str = str(raw_pose.get("quality", "TRACKING")).upper()
            quality = LocalizationQuality.TRACKING
            try:
                quality = LocalizationQuality(qual_str)
            except ValueError:
                pass

            pose = RobotPose(
                timestamp=ts,
                distance_m=effective_dist,
                x=effective_x,
                y=py,
                heading_rad=heading_rad,
                heading_deg=heading_deg,
                quality=quality,
                source="sidecar",
            )
            if dist is None:
                dist = effective_dist

    return SidecarFrameMetadata(
        timestamp=ts,
        distance_m=dist,
        robot_id=robot_id,
        camera_id=camera_id,
        pose=pose,
        extra=payload,
    )


def load_sidecar_for_image(image_path: Path) -> SidecarFrameMetadata | None:
    """Load per-image sidecar file if present (e.g., 0001.json for 0001.jpg)."""
    sidecar_path = image_path.with_suffix(".json")
    if not sidecar_path.exists() or not sidecar_path.is_file():
        return None

    try:
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return parse_sidecar_dict(data)
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return None


def load_global_directory_sidecar(directory_path: Path) -> tuple[dict[str, Any], dict[str, SidecarFrameMetadata]]:
    """Load directory-level metadata.json if present.

    Returns (global_defaults, per_frame_map).
    """
    global_meta_path = directory_path / "metadata.json"
    if not global_meta_path.exists() or not global_meta_path.is_file():
        return {}, {}

    try:
        data = json.loads(global_meta_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}, {}

        defaults: dict[str, Any] = {
            "robot_id": data.get("robot_id"),
            "camera_id": data.get("camera_id"),
            "distance_start_m": data.get("distance_start_m"),
            "distance_step_m": data.get("distance_step_m"),
        }

        frame_map: dict[str, SidecarFrameMetadata] = {}
        raw_frames = data.get("frames")
        if isinstance(raw_frames, dict):
            for key, val in raw_frames.items():
                if isinstance(val, dict):
                    frame_map[str(key)] = parse_sidecar_dict(val)

        return defaults, frame_map
    except (json.JSONDecodeError, OSError, ValueError):
        return {}, {}
