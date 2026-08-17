# Day 5.5 — Dataset Acquisition & Training Workflow

## Goal

Create a reproducible path from approved, labeled inspection images to a
validated train/validation/test dataset.

## Workflow

```text
approved source images
        +
approved YOLO labels
        ↓
pair collection
        ↓
seeded train/val/test split
        ↓
Day 5.4 validation
        ↓
class distribution
        ↓
SHA-256 manifest
        ↓
training-ready dataset
```

## Default split

```text
70% train
20% validation
10% test
```

The split uses a fixed seed so it can be reproduced.

## Important data rule

Do not put near-duplicate frames from the same short video segment into
different splits. Otherwise the test score can be artificially inflated.

The preferred unit for splitting is a video sequence / inspection segment,
not an individual frame, whenever the source data makes that possible.

## Provenance

`manifest.json` records a SHA-256 hash for every image, which provides a
simple reproducibility/provenance check.

## Run

Prepare from an approved directory containing matching image/label pairs:

```powershell
python -m scripts.prepare_dataset --source <approved-data-dir>
```

Then validate:

```powershell
python -m scripts.validate_dataset --dataset-dir dataset
```

Training must not start until the resulting dataset is reviewed.
