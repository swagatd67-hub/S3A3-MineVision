# Day 5.5.1 — Sewer-ML Train00 Subset Manifest

This step creates a deterministic, class-aware manifest from the Sewer-ML
training CSV for images known to be present in `train00.zip`.

The selection is multi-label aware: one image is kept once even if it belongs
to multiple target classes.

Current target caps:

```text
RB  2000
OB  2000
DE   318
FS  2000
RO   930
IN   161
AF  2000
BE  2000
FO   235
ND  2000
```

Seed: `42`

The output is:

```text
approved-data/sewer-ml/train00_subset.csv
```

This is only a manifest. It does not download images and does not alter the
original Sewer-ML CSV.
