# Day 4.4 — Actual Frame/Image Storage

## Goal

Persist the actual camera image together with the synchronized frame metadata.

## Storage layout

```text
video/storage/
└── M-XXXX/
    ├── frame-000001.jpg
    ├── frame-000002.jpg
    └── ...
```

Metadata remains in the mission JSONL file:

```text
video/storage/M-XXXX.jsonl
```

Each metadata record points to the corresponding image path.

## New endpoint

```text
POST /api/v1/video/frames/image
```

Multipart form fields:

- `mission_id`
- `frame_index`
- `timestamp`
- `distance_m`
- `source`
- `image`

Supported image types:

- JPEG
- PNG

## Retrieval

Metadata:

```text
GET /api/v1/video/missions/{mission_id}/frames/{frame_index}
```

Image:

```text
GET /api/v1/video/missions/{mission_id}/frames/{frame_index}/image
```

## Why this matters

The pipeline now has a real inspection artifact:

```text
camera
  ↓
image file
  +
mission_id
timestamp
distance_m
  ↓
stored inspection frame
```

Later the AI detector can consume the stored image and attach a detection to the
same frame and physical pipe distance.

## Storage strategy

We should not permanently save every 30 FPS frame for a long mission. The
pipeline will later use frame sampling/keyframes and event-triggered storage to
control storage volume.
