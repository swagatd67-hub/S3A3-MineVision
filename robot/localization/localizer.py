"""Deterministic First-Generation PipeVision Robot Localizer."""

from __future__ import annotations

import math
from datetime import datetime

from robot.localization.exceptions import LocalizationUpdateError
from robot.localization.models import LocalizationQuality, RobotPose
from robot.telemetry.models import RobotTelemetry


class RobotLocalizer:
    """Incremental localizer converting RobotTelemetry streams into RobotPose trajectories.

    Pipe Coordinates:
        Longitudinal axis (x) = distance_m along pipe (meters)
        Lateral axis (y) = 0.0 (meters, no lateral measurement)
        Relative Heading (yaw) = Integrated gyro angular rate gz (radians / degrees)
    """

    def __init__(self, max_allowed_dt_seconds: float = 300.0) -> None:
        self.max_allowed_dt_seconds = max_allowed_dt_seconds
        self._current_pose: RobotPose | None = None
        self._trajectory: list[RobotPose] = []
        self._accumulated_heading_rad: float = 0.0
        self._last_distance_m: float = 0.0
        self._last_timestamp: datetime | None = None
        self._quality: LocalizationQuality = LocalizationQuality.INITIALIZING

    @property
    def current_pose(self) -> RobotPose | None:
        """Return current estimated robot pose."""
        return self._current_pose

    @property
    def trajectory(self) -> tuple[RobotPose, ...]:
        """Return ordered tuple of immutable RobotPose records."""
        return tuple(self._trajectory)

    @property
    def quality(self) -> LocalizationQuality:
        """Return current localization tracking quality."""
        return self._quality

    def reset(self) -> None:
        """Reset localizer state, heading accumulator, and trajectory history."""
        self._current_pose = None
        self._trajectory.clear()
        self._accumulated_heading_rad = 0.0
        self._last_distance_m = 0.0
        self._last_timestamp = None
        self._quality = LocalizationQuality.INITIALIZING

    def update(self, telemetry: RobotTelemetry) -> RobotPose:
        """Update robot localization pose incrementally from a RobotTelemetry packet."""
        if not isinstance(telemetry, RobotTelemetry):
            raise LocalizationUpdateError(
                f"Expected RobotTelemetry instance, got {type(telemetry).__name__}."
            )

        ts = telemetry.timestamp
        dist_present = telemetry.distance_m is not None
        imu_present = telemetry.imu is not None

        # Determine distance
        if dist_present:
            dist = float(telemetry.distance_m)  # type: ignore[arg-type]
            self._last_distance_m = dist
        else:
            dist = self._last_distance_m

        # Handle time delta (dt) and heading integration
        dt: float | None = None
        dt_invalid = False
        dt_unreasonable = False

        if ts is not None and self._last_timestamp is not None:
            raw_dt = (ts - self._last_timestamp).total_seconds()
            if raw_dt < 0:
                # Out-of-order timestamp
                dt_invalid = True
            elif raw_dt == 0:
                # Repeated timestamp - zero dt
                dt = 0.0
            elif raw_dt > self.max_allowed_dt_seconds:
                # Unreasonable dt (e.g. gap > 5 minutes)
                dt_unreasonable = True
                dt = 0.0
            else:
                dt = raw_dt

        # Calculate relative heading if IMU gyro gz is available
        gz: float | None = None
        if imu_present and telemetry.imu is not None:
            gz = float(telemetry.imu.gz)

        # Update relative heading if dt is valid and positive
        if dt is not None and dt > 0.0 and gz is not None:
            delta_heading = gz * dt
            self._accumulated_heading_rad += delta_heading

        # Normalize heading to [-pi, pi]
        heading_rad = (self._accumulated_heading_rad + math.pi) % (2 * math.pi) - math.pi
        heading_deg = math.degrees(heading_rad)

        # Numerical safety checks
        x = dist
        y = 0.0

        for val_name, val in (
            ("x", x),
            ("y", y),
            ("heading_rad", heading_rad),
            ("heading_deg", heading_deg),
        ):
            if math.isnan(val) or math.isinf(val):
                self._quality = LocalizationQuality.INVALID
                raise LocalizationUpdateError(
                    f"Numerical calculation produced NaN or Inf for {val_name}."
                )

        # Determine quality and source metadata
        if dt_invalid:
            quality = LocalizationQuality.INVALID
            source = "out_of_order_timestamp"
        elif dt_unreasonable:
            quality = LocalizationQuality.DEGRADED
            source = "unreasonable_dt_gap"
        elif ts is None:
            quality = LocalizationQuality.DEGRADED
            source = "missing_timestamp"
        elif dist_present and imu_present:
            quality = LocalizationQuality.TRACKING
            source = "odometry+imu"
        elif dist_present and not imu_present:
            quality = LocalizationQuality.DEGRADED
            source = "odometry_only"
        elif not dist_present and imu_present:
            quality = LocalizationQuality.DEGRADED
            source = "imu_only"
        else:
            quality = LocalizationQuality.DEGRADED
            source = "none"

        pose = RobotPose(
            timestamp=ts,
            distance_m=x,
            x=x,
            y=y,
            heading_rad=heading_rad,
            heading_deg=heading_deg,
            quality=quality,
            source=source,
        )

        # Only update timestamp if ts is present and valid
        if ts is not None and not dt_invalid:
            self._last_timestamp = ts

        self._quality = quality
        self._current_pose = pose

        # Append to trajectory for valid updates (exclude invalid out-of-order dt)
        if not dt_invalid:
            self._trajectory.append(pose)

        return pose
