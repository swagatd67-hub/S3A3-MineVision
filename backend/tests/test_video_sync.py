from datetime import datetime, timedelta, timezone

from backend.app.services.video.synchronization import (
    TelemetryPosition,
    synchronize_frame,
    synchronize_frames,
)


def ts(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def test_interpolates_distance_between_telemetry_samples():
    telemetry = [
        TelemetryPosition(ts(0), 0.0, "M-001"),
        TelemetryPosition(ts(1), 0.15, "M-001"),
    ]

    synced = synchronize_frame(
        frame_index=15,
        timestamp=ts(0.5),
        mission_id="M-001",
        telemetry=telemetry,
    )

    assert synced is not None
    assert synced.distance_m == 0.075
    assert synced.interpolation == "linear"


def test_uses_nearest_sample_inside_allowed_gap():
    telemetry = [TelemetryPosition(ts(10), 5.0, "M-001")]

    synced = synchronize_frame(
        frame_index=100,
        timestamp=ts(10.2),
        mission_id="M-001",
        telemetry=telemetry,
        max_gap_ms=500,
    )

    assert synced is not None
    assert synced.distance_m == 5.0


def test_rejects_frame_outside_allowed_gap():
    telemetry = [TelemetryPosition(ts(10), 5.0, "M-001")]

    synced = synchronize_frame(
        frame_index=100,
        timestamp=ts(11.0),
        mission_id="M-001",
        telemetry=telemetry,
        max_gap_ms=500,
    )

    assert synced is None


def test_does_not_mix_missions():
    telemetry = [
        TelemetryPosition(ts(0), 100.0, "M-OTHER"),
        TelemetryPosition(ts(1), 200.0, "M-OTHER"),
    ]

    synced = synchronize_frame(
        frame_index=1,
        timestamp=ts(0.5),
        mission_id="M-001",
        telemetry=telemetry,
    )

    assert synced is None


def test_sync_multiple_frames():
    start = ts(100)
    telemetry = [
        TelemetryPosition(start, 10.0, "M-002"),
        TelemetryPosition(start + timedelta(seconds=2), 12.0, "M-002"),
    ]

    frames = [
        (0, start),
        (1, start + timedelta(seconds=1)),
        (2, start + timedelta(seconds=2)),
    ]

    synced = synchronize_frames(frames, telemetry, mission_id="M-002")

    assert [item.distance_m for item in synced] == [10.0, 11.0, 12.0]
