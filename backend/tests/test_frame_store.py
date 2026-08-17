from datetime import datetime, timezone

from backend.app.services.video.frame_store import (
    FrameMetadata,
    FrameMetadataStore,
)


def test_frame_store_round_trip(tmp_path):
    store = FrameMetadataStore(tmp_path)

    item = FrameMetadata(
        mission_id="M-001",
        frame_index=42,
        timestamp=datetime(2026, 8, 17, tzinfo=timezone.utc),
        distance_m=7.575,
        source="webcam",
        frame_path="video/storage/M-001/frame-000042.jpg",
    )

    store.append(item)

    found = store.get("M-001", 42)

    assert found is not None
    assert found.mission_id == "M-001"
    assert found.frame_index == 42
    assert found.distance_m == 7.575
    assert found.source == "webcam"


def test_frame_store_is_mission_scoped(tmp_path):
    store = FrameMetadataStore(tmp_path)

    timestamp = datetime(2026, 8, 17, tzinfo=timezone.utc)

    store.append(FrameMetadata("M-001", 1, timestamp, 1.0, "webcam"))
    store.append(FrameMetadata("M-002", 1, timestamp, 99.0, "webcam"))

    assert store.get("M-001", 1).distance_m == 1.0
    assert store.get("M-002", 1).distance_m == 99.0


def test_missing_frame_returns_none(tmp_path):
    store = FrameMetadataStore(tmp_path)

    assert store.get("M-001", 999) is None
