"""Camera Calibration Abstraction & Utilities.

DOCUMENTATION — REQUIRED PHYSICAL CAMERA HANDOFF:
When physical hardware is assembled, camera calibration MUST provide:
1. Intrinsic parameters: fx, fy (focal lengths in pixels), cx, cy (principal point pixel coordinates).
2. Distortion coefficients: Radial (k1, k2), Tangential (p1, p2) following OpenCV pinhole camera model.
3. Image dimensions: width x height in pixels (e.g. 1920x1080).
4. Physical mounting offset relative to robot crawler center (dx, dy, dz, pitch, roll, yaw).
"""

from __future__ import annotations

import numpy as np

from reconstruction.exceptions import CalibrationError
from reconstruction.models import CameraCalibration


class CameraCalibrationModel:
    """Wrapper and math helper for CameraCalibration models."""

    def __init__(self, calibration: CameraCalibration) -> None:
        self.calibration = calibration
        self._validate()

    def _validate(self) -> None:
        """Validate calibration parameters."""
        if self.calibration.image_width <= 0 or self.calibration.image_height <= 0:
            raise CalibrationError("Image dimensions must be positive integers.")
        if self.calibration.fx <= 0 or self.calibration.fy <= 0:
            raise CalibrationError("Focal length parameters (fx, fy) must be positive.")

    @property
    def camera_matrix(self) -> np.ndarray:
        """Get 3x3 intrinsic camera matrix K."""
        return np.array(
            [
                [self.calibration.fx, 0.0, self.calibration.cx],
                [0.0, self.calibration.fy, self.calibration.cy],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

    @property
    def distortion_coeffs(self) -> np.ndarray:
        """Get distortion vector [k1, k2, p1, p2]."""
        return np.array(
            [
                self.calibration.k1,
                self.calibration.k2,
                self.calibration.p1,
                self.calibration.p2,
            ],
            dtype=np.float64,
        )

    def is_synthetic(self) -> bool:
        """Return true if calibration is synthetic test fixture."""
        return self.calibration.calibration_status == "SYNTHETIC_TEST"


def create_synthetic_test_calibration(
    camera_id: str = "SYNTHETIC_TEST_CAM",
    width: int = 1920,
    height: int = 1080,
    focal_length_px: float = 1200.0,
) -> CameraCalibration:
    """Create explicit synthetic camera calibration for deterministic unit testing.

    IMPORTANT: Marked as SYNTHETIC_TEST. Must never be used as physical hardware calibration.
    """
    return CameraCalibration(
        camera_id=camera_id,
        image_width=width,
        image_height=height,
        fx=focal_length_px,
        fy=focal_length_px,
        cx=width / 2.0,
        cy=height / 2.0,
        k1=0.0,
        k2=0.0,
        p1=0.0,
        p2=0.0,
        calibration_status="SYNTHETIC_TEST",
        calibration_version="v1_synthetic",
    )
