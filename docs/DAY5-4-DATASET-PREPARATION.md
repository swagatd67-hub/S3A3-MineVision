# Day 5.4 — Inspection Dataset Preparation & Validation

## Goal

Prepare a clean YOLO dataset for the PipeVision domain-specific defect model
before training.

## Classes

```text
0 blockage
1 debris
2 crack
3 corrosion
4 sediment
5 structural_damage
```

## Validator checks

- image/label pairing
- unreadable images
- orphan labels
- YOLO label field count
- class ID range
- normalized coordinates
- positive width/height
- bounding-box bounds

Run:

```powershell
python -m scripts.validate_dataset --dataset-dir dataset
```

Do not train until the dataset passes validation and the annotations have been
reviewed for quality and class balance.
