from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TelemetryPosition:
    timestamp: datetime
    distance_m: float
    mission_id: str


@dataclass(frozen=True)
class SyncedFrame:
    frame_index: int
    timestamp: datetime
    distance_m: float
    mission_id: str
    interpolation: str
    source_delta_ms: float


def synchronize_frame(
    *,
    frame_index: int,
    timestamp: datetime,
    mission_id: str,
    telemetry: Sequence[TelemetryPosition] | Iterable[TelemetryPosition],
    max_gap_ms: float = 1000.0,
) -> SyncedFrame | None:
    rows = sorted(
        [p for p in telemetry if p.mission_id == mission_id],
        key=lambda p: p.timestamp,
    )

    if not rows:
        return None

    timestamps = [p.timestamp for p in rows]
    position = bisect_left(timestamps, timestamp)

    if position == 0:
        delta_ms = abs((rows[0].timestamp - timestamp).total_seconds() * 1000.0)
        if delta_ms > max_gap_ms:
            return None
        return SyncedFrame(
            frame_index=frame_index,
            timestamp=timestamp,
            distance_m=rows[0].distance_m,
            mission_id=mission_id,
            interpolation="nearest_before",
            source_delta_ms=delta_ms,
        )

    if position == len(rows):
        delta_ms = abs((timestamp - rows[-1].timestamp).total_seconds() * 1000.0)
        if delta_ms > max_gap_ms:
            return None
        return SyncedFrame(
            frame_index=frame_index,
            timestamp=timestamp,
            distance_m=rows[-1].distance_m,
            mission_id=mission_id,
            interpolation="nearest_after",
            source_delta_ms=delta_ms,
        )

    before = rows[position - 1]
    after = rows[position]

    total_s = (after.timestamp - before.timestamp).total_seconds()
    if total_s <= 0:
        return SyncedFrame(
            frame_index=frame_index,
            timestamp=timestamp,
            distance_m=before.distance_m,
            mission_id=mission_id,
            interpolation="duplicate_timestamp",
            source_delta_ms=0.0,
        )

    elapsed_s = (timestamp - before.timestamp).total_seconds()
    ratio = max(0.0, min(1.0, elapsed_s / total_s))
    distance = before.distance_m + (after.distance_m - before.distance_m) * ratio

    nearest_delta_ms = min(
        abs((timestamp - before.timestamp).total_seconds() * 1000.0),
        abs((after.timestamp - timestamp).total_seconds() * 1000.0),
    )

    if nearest_delta_ms > max_gap_ms:
        return None

    return SyncedFrame(
        frame_index=frame_index,
        timestamp=timestamp,
        distance_m=distance,
        mission_id=mission_id,
        interpolation="linear",
        source_delta_ms=nearest_delta_ms,
    )


def synchronize_frames(
    frames: Iterable[tuple[int, datetime]],
    telemetry: Sequence[TelemetryPosition] | Iterable[TelemetryPosition],
    *,
    mission_id: str,
    max_gap_ms: float = 1000.0,
) -> list[SyncedFrame]:
    telemetry = list(telemetry)
    result: list[SyncedFrame] = []

    for frame_index, timestamp in frames:
        synced = synchronize_frame(
            frame_index=frame_index,
            timestamp=timestamp,
            mission_id=mission_id,
            telemetry=telemetry,
            max_gap_ms=max_gap_ms,
        )
        if synced is not None:
            result.append(synced)

    return result
