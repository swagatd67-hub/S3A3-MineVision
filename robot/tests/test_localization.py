"""Comprehensive Unit Tests for Robot Localization Layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from robot.localization import (
    LocalizationQuality,
    LocalizationUpdateError,
    RobotLocalizer,
    RobotPose,
)
from robot.telemetry import (
    IMUData,
    RobotTelemetry,
    parse_telemetry,
)
from robot.transport.simulator import SimulatorTransport


def test_initial_pose_and_quality() -> None:
    loc = RobotLocalizer()
    assert loc.current_pose is None
    assert loc.trajectory == ()
    assert loc.quality == LocalizationQuality.INITIALIZING


def test_sequential_updates_and_trajectory() -> None:
    loc = RobotLocalizer()
    t0 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    # First update
    telemetry1 = RobotTelemetry(
        robot_id="PV-01",
        timestamp=t0,
        distance_m=1.0,
        imu=IMUData(ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=0.1),
    )
    pose1 = loc.update(telemetry1)

    assert isinstance(pose1, RobotPose)
    assert pose1.distance_m == 1.0
    assert pose1.x == 1.0
    assert pose1.y == 0.0
    assert pose1.heading_rad == 0.0  # Initial sample -> dt not established yet
    assert pose1.quality == LocalizationQuality.TRACKING
    assert pose1.source == "odometry+imu"

    # Second update (1 second later, gz = 0.1 rad/s)
    telemetry2 = RobotTelemetry(
        robot_id="PV-01",
        timestamp=t0 + timedelta(seconds=1.0),
        distance_m=1.5,
        imu=IMUData(ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=0.1),
    )
    pose2 = loc.update(telemetry2)

    assert pose2.distance_m == 1.5
    assert pose2.x == 1.5
    assert pytest.approx(pose2.heading_rad, rel=1e-3) == 0.1
    assert pose2.quality == LocalizationQuality.TRACKING

    assert len(loc.trajectory) == 2
    assert loc.trajectory[0] == pose1
    assert loc.trajectory[1] == pose2


def test_distance_only_localization() -> None:
    loc = RobotLocalizer()
    t0 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    telemetry = RobotTelemetry(
        robot_id="PV-01",
        timestamp=t0,
        distance_m=5.0,
        imu=None,
    )
    pose = loc.update(telemetry)

    assert pose.distance_m == 5.0
    assert pose.x == 5.0
    assert pose.y == 0.0
    assert pose.heading_rad == 0.0
    assert pose.quality == LocalizationQuality.DEGRADED
    assert pose.source == "odometry_only"


def test_missing_distance_localization() -> None:
    loc = RobotLocalizer()
    t0 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    # First update with distance
    loc.update(RobotTelemetry(robot_id="PV-01", timestamp=t0, distance_m=3.0))

    # Second update missing distance
    telemetry2 = RobotTelemetry(
        robot_id="PV-01",
        timestamp=t0 + timedelta(seconds=1.0),
        distance_m=None,
        imu=IMUData(ax=0.0, ay=0.0, az=9.81, gx=0.0, gy=0.0, gz=0.2),
    )
    pose2 = loc.update(telemetry2)

    assert pose2.distance_m == 3.0  # Keeps previous distance
    assert pose2.quality == LocalizationQuality.DEGRADED
    assert pose2.source == "imu_only"
    assert pytest.approx(pose2.heading_rad, rel=1e-3) == 0.2


def test_both_missing_distance_and_imu() -> None:
    loc = RobotLocalizer()
    t0 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    telemetry = RobotTelemetry(robot_id="PV-01", timestamp=t0, distance_m=None, imu=None)
    pose = loc.update(telemetry)

    assert pose.distance_m == 0.0
    assert pose.quality == LocalizationQuality.DEGRADED
    assert pose.source == "none"


def test_missing_timestamp() -> None:
    loc = RobotLocalizer()
    telemetry = RobotTelemetry(robot_id="PV-01", timestamp=None, distance_m=2.0)
    pose = loc.update(telemetry)

    assert pose.distance_m == 2.0
    assert pose.quality == LocalizationQuality.DEGRADED
    assert pose.source == "missing_timestamp"


def test_zero_dt_repeated_timestamp() -> None:
    loc = RobotLocalizer()
    t0 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    telemetry1 = RobotTelemetry(robot_id="PV-01", timestamp=t0, distance_m=1.0)
    loc.update(telemetry1)

    # Same timestamp
    telemetry2 = RobotTelemetry(robot_id="PV-01", timestamp=t0, distance_m=1.0)
    pose2 = loc.update(telemetry2)

    assert pose2.distance_m == 1.0
    assert len(loc.trajectory) == 2


def test_negative_dt_out_of_order_timestamp() -> None:
    loc = RobotLocalizer()
    t0 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    loc.update(RobotTelemetry(robot_id="PV-01", timestamp=t0, distance_m=2.0))

    # Out of order timestamp (10 seconds earlier)
    telemetry_old = RobotTelemetry(
        robot_id="PV-01",
        timestamp=t0 - timedelta(seconds=10.0),
        distance_m=1.0,
    )
    pose_invalid = loc.update(telemetry_old)

    assert pose_invalid.quality == LocalizationQuality.INVALID
    assert pose_invalid.source == "out_of_order_timestamp"
    # Invalid pose is not appended to trajectory history
    assert len(loc.trajectory) == 1


def test_unreasonable_dt_gap() -> None:
    loc = RobotLocalizer()
    t0 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    loc.update(RobotTelemetry(robot_id="PV-01", timestamp=t0, distance_m=1.0))

    # 10 minutes gap (> 300s limit)
    telemetry_gap = RobotTelemetry(
        robot_id="PV-01",
        timestamp=t0 + timedelta(seconds=600.0),
        distance_m=5.0,
    )
    pose_gap = loc.update(telemetry_gap)

    assert pose_gap.quality == LocalizationQuality.DEGRADED
    assert pose_gap.source == "unreasonable_dt_gap"


def test_reset_clears_localizer() -> None:
    loc = RobotLocalizer()
    t0 = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

    loc.update(RobotTelemetry(robot_id="PV-01", timestamp=t0, distance_m=10.0))
    assert loc.current_pose is not None
    assert len(loc.trajectory) == 1

    loc.reset()

    assert loc.current_pose is None
    assert loc.trajectory == ()
    assert loc.quality == LocalizationQuality.INITIALIZING


def test_invalid_telemetry_instance_type() -> None:
    loc = RobotLocalizer()
    with pytest.raises(LocalizationUpdateError, match="Expected RobotTelemetry"):
        loc.update("not_a_telemetry_object")  # type: ignore[arg-type]


def test_simulator_telemetry_integration() -> None:
    sim = SimulatorTransport(robot_id="PV-SIM-LOC")
    sim.connect()

    loc = RobotLocalizer()

    # Step simulator multiple times and feed into localizer
    poses: list[RobotPose] = []
    for _ in range(5):
        raw_packet = sim.step()
        telemetry = parse_telemetry(raw_packet)
        assert telemetry is not None
        pose = loc.update(telemetry)
        poses.append(pose)

    sim.disconnect()

    assert len(poses) == 5
    # Verify distance increases over time
    assert poses[-1].distance_m >= poses[0].distance_m
    assert poses[-1].x == poses[-1].distance_m
    assert poses[-1].y == 0.0
    assert len(loc.trajectory) == 5
