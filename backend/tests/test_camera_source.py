"""Tests for configurable local network camera sources."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.services.video.source import ESP32CAMSource
from backend.app.services.video.streaming import esp32cam_mjpeg_proxy


def test_esp32cam_url_is_required_and_configurable() -> None:
    with pytest.raises(ValueError):
        ESP32CAMSource("")
    assert ESP32CAMSource("http://esp32cam.local:81/stream").url == "http://esp32cam.local:81/stream"


def test_esp32cam_proxy_returns_fallback_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*_args, **_kwargs):
        raise OSError("camera offline")

    monkeypatch.setattr("backend.app.services.video.source.urlopen", offline)
    source = ESP32CAMSource("http://192.168.1.50/stream")
    chunks = asyncio.run(_collect(esp32cam_mjpeg_proxy(source)))
    assert len(chunks) == 1
    assert b"--frame" in chunks[0]
    assert b"Content-Type: image/jpeg" in chunks[0]
    assert b"\xff\xd8" in chunks[0]


async def _collect(generator):
    return [chunk async for chunk in generator]
