"""Adapters for Offline Photos, Offline Videos, and Ingestion Results."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.services.inspection.models import (
        BatchIngestionResult,
        CanonicalInspectionFrame,
        VideoIngestionResult,
    )
from reconstruction.models import ReconstructionFrame


def canonical_frames_to_reconstruction_frames(
    canonical_frames: Sequence[CanonicalInspectionFrame],
) -> tuple[ReconstructionFrame, ...]:
    """Convert CanonicalInspectionFrame list into ReconstructionFrame sequence."""
    rec_frames: list[ReconstructionFrame] = []

    for i, cf in enumerate(canonical_frames):
        frame_id = cf.frame_id or f"frame_{i:04d}"
        rec_frames.append(
            ReconstructionFrame(
                frame_id=frame_id,
                frame_index=cf.frame_index if cf.frame_index is not None else i,
                timestamp=cf.timestamp if (cf.timestamp is None) or not isinstance(cf.timestamp, str) else None,
                image_path=cf.image_path,
                image_bytes=cf.image_bytes,
                pose=cf.pose,
                distance_m=cf.distance_m,
                source=cf.source,
            )
        )

    return tuple(rec_frames)


def batch_result_to_reconstruction_frames(
    batch_result: BatchIngestionResult,
) -> tuple[ReconstructionFrame, ...]:
    """Convert BatchIngestionResult into ReconstructionFrame sequence."""
    rec_frames: list[ReconstructionFrame] = []

    for res in batch_result.results:
        rec_frames.append(
            ReconstructionFrame(
                frame_id=res.frame_id,
                frame_index=res.frame_index,
                image_path=res.frame_path,
                distance_m=res.distance_m,
                source=res.source,
            )
        )

    return tuple(rec_frames)


def video_result_to_reconstruction_frames(
    video_result: VideoIngestionResult,
) -> tuple[ReconstructionFrame, ...]:
    """Convert VideoIngestionResult into ReconstructionFrame sequence."""
    rec_frames: list[ReconstructionFrame] = []

    for res in video_result.results:
        rec_frames.append(
            ReconstructionFrame(
                frame_id=res.frame_id,
                frame_index=res.frame_index,
                image_path=res.frame_path,
                distance_m=res.distance_m,
                source="video",
            )
        )

    return tuple(rec_frames)
