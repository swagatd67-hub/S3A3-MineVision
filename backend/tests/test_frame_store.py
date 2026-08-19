from datetime import datetime, timezone
from pathlib import Path

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

    store.append(
        FrameMetadata(
            "M-001",
            1,
            timestamp,
            1.0,
            "webcam",
        )
    )

    store.append(
        FrameMetadata(
            "M-002",
            1,
            timestamp,
            99.0,
            "webcam",
        )
    )

    first = store.get("M-001", 1)
    second = store.get("M-002", 1)

    assert first is not None
    assert second is not None

    assert first.distance_m == 1.0
    assert second.distance_m == 99.0


def test_missing_frame_returns_none(tmp_path):
    store = FrameMetadataStore(tmp_path)

    assert store.get("M-001", 999) is None


def test_save_image_writes_bytes(tmp_path):
    store = FrameMetadataStore(tmp_path)

    path = store.save_image(
        mission_id="M-IMG",
        frame_index=7,
        image_bytes=b"\xff\xd8fake-jpeg\xff\xd9",
        extension=".jpg",
    )

    image_path = Path(path)

    assert image_path.exists()
    assert image_path.read_bytes() == b"\xff\xd8fake-jpeg\xff\xd9"


def test_image_path_returns_stored_image(tmp_path, monkeypatch):
    store = FrameMetadataStore(tmp_path)
    monkeypatch.chdir(tmp_path.parent)

    relative = store.save_image(
        mission_id="M-IMG2",
        frame_index=3,
        image_bytes=b"PNGDATA",
        extension=".png",
    )

    store.append(
        FrameMetadata(
            mission_id="M-IMG2",
            frame_index=3,
            timestamp=datetime.now(timezone.utc),
            distance_m=2.5,
            source="webcam",
            frame_path=relative,
        )
    )

    path = store.image_path("M-IMG2", 3)

    assert path is not None
    assert path.exists()
    assert path.read_bytes() == b"PNGDATA"
