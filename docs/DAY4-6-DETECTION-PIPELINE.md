# Day 4.6 — Visual Detection Pipeline

## Goal

Introduce a stable visual-detection contract without coupling PipeVision to one
specific model implementation.

## Pipeline

```text
stored frame
    ↓
detector adapter
    ↓
detections
    ↓
mission + frame + distance
    ↓
inspection event
```

## Detection contract

Each detection contains:

- label
- confidence
- bounding box

Each result contains:

- model
- image dimensions
- inference time when available
- detections

## Detectors

`NullDetector` is deterministic and is used for CI/pipeline tests.

`UltralyticsDetector` is the adapter for a general-purpose YOLO model. A
custom pipe-defect model can later replace the weights without changing the
frame storage or API contract.

## Endpoint

```text
POST /api/v1/video/missions/{mission_id}/frames/{frame_index}/detect
```

Pipeline verification uses:

```text
?model=null
```

A general pretrained YOLO model is not a trained pipe-defect detector. Until a
domain-specific model is trained, its output is only a computer-vision
pipeline demonstration.
