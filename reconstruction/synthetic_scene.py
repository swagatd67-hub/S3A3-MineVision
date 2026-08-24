"""Deterministic Synthetic Cylindrical Pipe Scene Generator for Algorithm & Unit Validation."""

from __future__ import annotations

from datetime import datetime, timezone

from reconstruction.calibration import create_synthetic_test_calibration
from reconstruction.models import CameraCalibration, ReconstructionFrame
from robot.localization.models import LocalizationQuality, RobotPose


class SyntheticPipeSceneGenerator:
    """Generates synthetic pipe geometry, camera trajectory, and frame metadata for 3D reconstruction testing."""

    def __init__(
        self,
        pipe_length_m: float = 10.0,
        pipe_diameter_mm: float = 300.0,
        frame_count: int = 21,
        camera_calibration: CameraCalibration | None = None,
    ) -> None:
        self.pipe_length_m = pipe_length_m
        self.pipe_diameter_mm = pipe_diameter_mm
        self.frame_count = max(2, frame_count)
        self.camera_calibration = (
            camera_calibration or create_synthetic_test_calibration()
        )

    def generate_synthetic_frames(
        self,
        mission_id: str = "synthetic_mission_001",
    ) -> tuple[ReconstructionFrame, ...]:
        """Generate a sequence of synthetic ReconstructionFrames with exact ground-truth poses."""
        frames: list[ReconstructionFrame] = []
        step_dist = self.pipe_length_m / (self.frame_count - 1)
        base_time = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(self.frame_count):
            dist = i * step_dist
            pose = RobotPose(
                timestamp=base_time,
                distance_m=dist,
                x=dist,
                y=0.0,
                heading_rad=0.0,
                heading_deg=0.0,
                quality=LocalizationQuality.TRACKING,
                source="synthetic_ground_truth",
            )

            frames.append(
                ReconstructionFrame(
                    frame_id=f"syn_frame_{i:04d}",
                    frame_index=i,
                    timestamp=base_time,
                    image_path=f"/tmp/synthetic_frames/frame_{i:04d}.png",
                    pose=pose,
                    distance_m=dist,
                    source="simulator",
                )
            )

        return tuple(frames)
