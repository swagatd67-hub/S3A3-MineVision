# Day 5.2 — Detector → Defect Event Integration

## Goal

Convert model-agnostic detector output into the PipeVision defect event contract
created in Day 5.1.

## Pipeline

```text
vision detector
    ↓
RawDetection
    ↓
label → DefectClass
    ↓
confidence filter
    ↓
DefectDetection
    ↓
DetectionEvent
```

Every event carries the mission-spatial identity:

```text
mission_id
frame_index
timestamp
distance_m
```

## Safety-oriented behavior

- Unknown labels map to `unknown`.
- Weak predictions can be filtered using a configurable confidence threshold.
- New detections start as `candidate`.
- Image preprocessing usability is preserved on the event.
- No model prediction is automatically marked as `confirmed`.

## Next step

Day 5.3 connects the detector adapter to a real model and evaluates its output
on inspection imagery.
