# Day 5.1 — Pipe Defect Taxonomy and Detection Contract

## Goal

Define the visual-inspection classes and the event contract before introducing a
domain-specific detection model.

## Initial prototype classes

```text
blockage
debris
crack
corrosion
sediment
structural_damage
```

`unknown` is reserved for detections that do not map cleanly to an approved
class.

## Detection lifecycle

```text
model prediction
    ↓
candidate
    ↓
cross-check / human review / additional evidence
    ↓
confirmed or rejected
```

The model should not be treated as an authoritative diagnosis merely because
its confidence is high.

## Detection event

A visual event carries:

```text
mission_id
frame_index
timestamp
distance_m
source
model
preprocessing_usable
defect_class
confidence
bounding box
disposition
```

The critical spatial link remains:

```text
mission_id + frame_index + distance_m
```

This allows a detection to be joined to telemetry, video and later mapping.

## Day 5 model strategy

The detection adapter from Day 4.6 remains the model boundary.

Next steps:

1. keep the deterministic `NullDetector` for tests
2. evaluate a general YOLO baseline on sample images
3. prepare a domain-specific dataset
4. train/fine-tune a pipe-defect model
5. evaluate precision, recall and per-class performance
6. integrate only after the event contract is stable
