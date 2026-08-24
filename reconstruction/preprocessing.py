"""Image Preprocessing and Feature Quality Assessment for 3D Pipe Reconstruction."""

from __future__ import annotations

import numpy as np

from reconstruction.calibration import CameraCalibrationModel
from reconstruction.models import CameraCalibration


class ReconstructionImagePreprocessor:
    """Explicit image preprocessing stage dedicated to 3D pipe reconstruction."""

    def __init__(self, calibration: CameraCalibration | None = None) -> None:
        self.calibration_model = (
            CameraCalibrationModel(calibration) if calibration is not None else None
        )

    def undistort(self, image: np.ndarray) -> np.ndarray:
        """Undistort raw camera image using intrinsic & distortion parameters."""
        if self.calibration_model is None:
            return image

        # Pass-through if no distortion coefficients
        k1 = self.calibration_model.calibration.k1
        k2 = self.calibration_model.calibration.k2
        if abs(k1) < 1e-7 and abs(k2) < 1e-7:
            return image

        # If OpenCV is available, apply cv2.undistort, otherwise fallback gracefully
        try:
            import cv2  # type: ignore

            k = self.calibration_model.camera_matrix
            d = self.calibration_model.distortion_coeffs
            return cv2.undistort(image, k, d)
        except ImportError:
            return image

    def assess_feature_quality(self, image: np.ndarray) -> dict[str, float]:
        """Compute image feature variance / sharpness score for feature matching."""
        if image.size == 0:
            return {"mean_brightness": 0.0, "sharpness": 0.0}

        # Convert to grayscale if RGB/BGR
        if len(image.shape) == 3:
            gray = np.mean(image, axis=2).astype(np.float64)
        else:
            gray = image.astype(np.float64)

        brightness = float(np.mean(gray))

        # Variance of Laplacian approximation for focus/sharpness
        gy, gx = np.gradient(gray)
        sharpness = float(np.var(gx) + np.var(gy))

        return {
            "mean_brightness": round(brightness, 2),
            "sharpness": round(sharpness, 2),
        }
