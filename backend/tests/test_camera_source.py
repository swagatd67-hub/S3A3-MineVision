"""Tests for configurable local network camera sources."""

from __future__ import annotations

import asyncio
from io import BytesIO

import pytest

from backend.app.services.video.source import ESP32CAMSource
from backend.app.services.video.streaming import esp32cam_mjpeg_proxy


def test_esp32cam_url_is_required_and_configurable() -> None:
    with pytest.raises(ValueError, match="ESP32-CAM URL or snapshot URL must be configured"):
        ESP32CAMSource("", snapshot_url="")
    source = ESP32CAMSource("http://esp32cam.local:81/stream", snapshot_url="http://esp32cam.local/capture")
    assert source.url == "http://esp32cam.local:81/stream"
    assert source.snapshot_url == "http://esp32cam.local/capture"


def test_esp32cam_snapshot_fetch_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"

    class FakeResponse:
        def __enter__(self):
            return BytesIO(fake_jpeg)

        def __exit__(self, *_args):
            pass

    def mock_urlopen(*_args, **_kwargs):
        return FakeResponse()

    monkeypatch.setattr("backend.app.services.video.source.urlopen", mock_urlopen)
    source = ESP32CAMSource(snapshot_url="http://192.168.137.158/capture")
    jpeg_data = source.fetch_snapshot()
    assert jpeg_data == fake_jpeg


def test_esp32cam_proxy_snapshot_fallback_when_stream_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    fetch_count = 0

    class FakeResponse:
        def __enter__(self):
            return BytesIO(fake_jpeg)

        def __exit__(self, *_args):
            pass

    def mock_urlopen(req, *_args, **_kwargs):
        nonlocal fetch_count
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "stream" in url:
            raise OSError("Stream port 81 timed out")
        fetch_count += 1
        if fetch_count > 2:
            raise OSError("Stop polling")
        return FakeResponse()

    monkeypatch.setattr("backend.app.services.video.source.urlopen", mock_urlopen)
    source = ESP32CAMSource(
        url="http://192.168.137.158:81/stream",
        snapshot_url="http://192.168.137.158/capture",
    )
    chunks = asyncio.run(_collect_n(esp32cam_mjpeg_proxy(source, fps=30.0), max_chunks=2))
    assert len(chunks) == 2
    for chunk in chunks:
        assert b"--frame" in chunk
        assert b"Content-Type: image/jpeg" in chunk
        assert fake_jpeg in chunk


def test_esp32cam_proxy_returns_fallback_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*_args, **_kwargs):
        raise OSError("camera offline")

    monkeypatch.setattr("backend.app.services.video.source.urlopen", offline)
    source = ESP32CAMSource("http://192.168.1.50/stream", snapshot_url="http://192.168.1.50/capture")
    chunks = asyncio.run(_collect_n(esp32cam_mjpeg_proxy(source), max_chunks=1))
    assert len(chunks) == 1
    assert b"--frame" in chunks[0]
    assert b"Content-Type: image/jpeg" in chunks[0]
    assert b"\xff\xd8" in chunks[0]


async def _collect_n(generator, max_chunks: int = 1):
    items = []
    async for chunk in generator:
        items.append(chunk)
        if len(items) >= max_chunks:
            break
    return items
