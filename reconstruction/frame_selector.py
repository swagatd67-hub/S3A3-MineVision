"""Deterministic Frame Selection & Sequence Filtering for 3D Pipe Reconstruction."""

from __future__ import annotations

from collections.abc import Sequence

from reconstruction.models import ReconstructionFrame


class FrameSelector:
    """Deterministic selection of reconstruction frames based on spatial, temporal, and quality criteria."""

    def __init__(
        self,
        min_distance_step_m: float = 0.05,
        min_frame_step: int = 1,
        filter_duplicates: bool = True,
        require_valid_image: bool = True,
    ) -> None:
        self.min_distance_step_m = min_distance_step_m
        self.min_frame_step = min_frame_step
        self.filter_duplicates = filter_duplicates
        self.require_valid_image = require_valid_image

    def select_frames(
        self,
        frames: Sequence[ReconstructionFrame],
    ) -> tuple[ReconstructionFrame, ...]:
        """Filter input sequence of ReconstructionFrames into a deterministic, high-quality subset for 3D reconstruction."""
        if not frames:
            return ()

        selected: list[ReconstructionFrame] = []
        last_distance: float | None = None
        last_index: int | None = None
        last_image_path: str | None = None

        for frame in frames:
            # 1. Require image payload or path if configured
            if self.require_valid_image and not (frame.image_path or frame.image_bytes):
                continue

            # 2. Duplicate image path filtering
            if self.filter_duplicates and frame.image_path and frame.image_path == last_image_path:
                continue

            # 3. Minimum frame index step check
            if last_index is not None and (frame.frame_index - last_index) < self.min_frame_step:
                continue

            # 4. Spatial distance step check
            if frame.distance_m is not None and last_distance is not None:
                delta_dist = abs(frame.distance_m - last_distance)
                if delta_dist < self.min_distance_step_m:
                    continue

            # Frame passed selection criteria
            selected.append(frame)
            last_index = frame.frame_index
            if frame.distance_m is not None:
                last_distance = frame.distance_m
            if frame.image_path:
                last_image_path = frame.image_path

        return tuple(selected)
