# Day 4.5 — OpenCV Preprocessing

## Goal
Turn stored camera frames into consistent AI-ready images while measuring basic image quality.

## Pipeline
```text
stored image
  ↓
format normalization
  ↓
resize
  ↓
mild denoise
  ↓
LAB/CLAHE contrast normalization
  ↓
quality measurement
  ↓
AI-ready frame
```

## Quality metrics
- blur score (variance of Laplacian)
- brightness
- grayscale contrast
- usability flag
- quality reasons

The output remains a BGR NumPy image for downstream computer vision.

## CLI
```powershell
python -m scripts.preprocess_frame video\samples\test_frame.png video\storage\preprocessed.png
```
