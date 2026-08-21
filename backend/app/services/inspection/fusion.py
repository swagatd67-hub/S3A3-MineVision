"""Service Layer for Inspection Observation Fusion."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from backend.app.services.inspection.exceptions import (
    DistanceConflictError,
    InvalidPerceptionInputError,
)
from backend.app.services.inspection.models import (
    BoundingBox,
    FusedInspectionObservation,
    InspectionFrameMetadata,
    RawPerceptionItem,
)
from robot.localization.models import RobotPose


def _parse_timestamp_to_utc(val: str | datetime | None) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    if isinstance(val, str):
        try:
            cleaned = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None
    return None


def _generate_observation_id(
    mission_id: str,
    frame_index: int,
    model_name: str,
    class_code: str,
    box: BoundingBox | None,
    confidence: float,
) -> str:
    box_str = f"{box.x1:.1f}_{box.y1:.1f}_{box.x2:.1f}_{box.y2:.1f}" if box else "nobox"
    raw_key = f"{mission_id}:{frame_index}:{model_name}:{class_code}:{box_str}:{confidence:.4f}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:12]
    return f"obs-{digest}"


def adapt_perception_input(raw_input: Any) -> list[RawPerceptionItem]:
    """Adapt heterogeneous perception model outputs into normalized RawPerceptionItem objects.

    Supports:
        - RawPerceptionItem or list[RawPerceptionItem]
        - DetectionResult (YOLO object detection)
        - SewerMLResult (Sewer-ML multi-label classification)
        - DetectionEvent (backend defect event)
    """
    if raw_input is None:
        return []

    if isinstance(raw_input, RawPerceptionItem):
        return [raw_input]

    if isinstance(raw_input, list):
        items: list[RawPerceptionItem] = []
        for elem in raw_input:
            items.extend(adapt_perception_input(elem))
        return items

    # Check DetectionResult (YOLO)
    if hasattr(raw_input, "detections") and hasattr(raw_input, "model") and hasattr(raw_input, "image_width"):
        items = []
        model_name = str(getattr(raw_input, "model", "yolo"))
        for det in getattr(raw_input, "detections", []):
            label = getattr(det, "label", "unknown")
            conf = float(getattr(det, "confidence", 0.0))
            x1 = float(getattr(det, "x1", 0.0))
            y1 = float(getattr(det, "y1", 0.0))
            x2 = float(getattr(det, "x2", 0.0))
            y2 = float(getattr(det, "y2", 0.0))
            items.append(
                RawPerceptionItem(
                    class_code=label,
                    confidence=conf,
                    model_name=model_name,
                    model_version="yolo",
                    box=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    source_type="yolo",
                    detected=True,
                )
            )
        return items

    # Check SewerMLResult (Multi-label classification)
    if hasattr(raw_input, "decisions") and hasattr(raw_input, "detected_classes"):
        items = []
        model_version = str(getattr(raw_input, "model_version", "sewer-ml-e009"))
        for dec in getattr(raw_input, "decisions", []):
            detected = bool(getattr(dec, "detected", False))
            if detected:
                code = str(getattr(dec, "class_code", "unknown"))
                prob = float(getattr(dec, "probability", 0.0))
                thresh = float(getattr(dec, "threshold", 0.5))
                items.append(
                    RawPerceptionItem(
                        class_code=code,
                        confidence=prob,
                        model_name="sewer-ml-e009",
                        model_version=model_version,
                        threshold=thresh,
                        box=None,  # Multi-label classifier produces no pixel bounding box
                        source_type="sewer-ml",
                        detected=True,
                    )
                )
        return items

    # Check DetectionEvent
    if hasattr(raw_input, "detection") and hasattr(raw_input, "mission_id"):
        event_model = str(getattr(raw_input, "model", "defect_detector"))
        det = raw_input.detection
        defect_cls = getattr(det, "defect_class", "unknown")
        code = defect_cls.value if hasattr(defect_cls, "value") else str(defect_cls)
        conf = float(getattr(det, "confidence", 0.0))
        x1 = float(getattr(det, "x1", 0.0))
        y1 = float(getattr(det, "y1", 0.0))
        x2 = float(getattr(det, "x2", 0.0))
        y2 = float(getattr(det, "y2", 0.0))
        return [
            RawPerceptionItem(
                class_code=code,
                confidence=conf,
                model_name=event_model,
                model_version="v1",
                box=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                source_type=str(getattr(raw_input, "source", "detector")),
                detected=True,
            )
        ]

    raise InvalidPerceptionInputError(
        f"Unsupported perception input object type: {type(raw_input).__name__}"
    )


def fuse_observations(
    perception_input: Any,
    frame_metadata: InspectionFrameMetadata,
    robot_pose: RobotPose | None = None,
    distance_policy: str = "FRAME_PREFERRED",
    max_allowed_distance_conflict_m: float = 0.5,
) -> list[FusedInspectionObservation]:
    """Fuse AI perception outputs with spatial/temporal localization context.

    Parameters:
        perception_input: Raw perception result (DetectionResult, SewerMLResult, RawPerceptionItem, etc.)
        frame_metadata: Frame metadata (mission_id, frame_index, timestamp, distance_m)
        robot_pose: Optional robot localization pose (RobotPose)
        distance_policy: Policy for resolving distance conflict ('FRAME_PREFERRED', 'POSE_PREFERRED', 'STRICT')
        max_allowed_distance_conflict_m: Conflict threshold for 'STRICT' policy

    Returns:
        list[FusedInspectionObservation]: List of immutable fused observations.
    """

    items = adapt_perception_input(perception_input)
    if not items:
        return []

    # Timestamp Resolution: Frame timestamp preferred, fallback to pose timestamp
    frame_ts_utc = _parse_timestamp_to_utc(frame_metadata.timestamp)
    pose_ts_utc = robot_pose.timestamp if robot_pose is not None else None
    resolved_ts = frame_ts_utc if frame_ts_utc is not None else pose_ts_utc
    resolved_ts_iso = resolved_ts.isoformat() if resolved_ts is not None else None

    # Distance Resolution: Frame distance vs Pose distance
    frame_dist = (
        float(frame_metadata.distance_m)
        if frame_metadata.distance_m is not None
        else None
    )
    pose_dist = (
        float(robot_pose.distance_m)
        if robot_pose is not None and robot_pose.distance_m is not None
        else None
    )

    distance_conflict: float | None = None
    if frame_dist is not None and pose_dist is not None:
        distance_conflict = abs(frame_dist - pose_dist)

    if (
        distance_policy == "STRICT"
        and distance_conflict is not None
        and distance_conflict > max_allowed_distance_conflict_m
    ):
        raise DistanceConflictError(
            f"Distance conflict {distance_conflict:.3f}m exceeds max allowed threshold {max_allowed_distance_conflict_m}m."
        )

    if distance_policy == "POSE_PREFERRED" and pose_dist is not None:
        resolved_dist = pose_dist
    else:  # FRAME_PREFERRED (default)
        resolved_dist = frame_dist if frame_dist is not None else pose_dist

    # Localization Quality Resolution
    if robot_pose is None:
        loc_quality = "UNAVAILABLE"
    else:
        loc_quality = (
            robot_pose.quality.value
            if hasattr(robot_pose.quality, "value")
            else str(robot_pose.quality)
        )

    # Infer image dimensions if present in perception input
    img_width = frame_metadata.image_width
    img_height = frame_metadata.image_height
    if img_width is None and hasattr(perception_input, "image_width"):
        img_width = int(perception_input.image_width)
    if img_height is None and hasattr(perception_input, "image_height"):
        img_height = int(perception_input.image_height)

    fused_list: list[FusedInspectionObservation] = []
    for item in items:
        obs_id = _generate_observation_id(
            mission_id=frame_metadata.mission_id,
            frame_index=frame_metadata.frame_index,
            model_name=item.model_name,
            class_code=item.class_code,
            box=item.box,
            confidence=item.confidence,
        )

        fused_obs = FusedInspectionObservation(
            observation_id=obs_id,
            mission_id=frame_metadata.mission_id,
            frame_index=frame_metadata.frame_index,
            timestamp=resolved_ts,
            timestamp_iso=resolved_ts_iso,
            distance_m=resolved_dist,
            frame_distance_m=frame_dist,
            pose_distance_m=pose_dist,
            distance_conflict_m=distance_conflict,
            robot_pose=robot_pose,
            localization_quality=loc_quality,
            class_code=item.class_code,
            confidence=item.confidence,
            threshold=item.threshold,
            box=item.box,
            model_name=item.model_name,
            model_version=item.model_version,
            source_type=item.source_type,
            image_width=img_width,
            image_height=img_height,
        )
        fused_list.append(fused_obs)

    return fused_list
