# Day 4.3 — Synchronized Frame Metadata Storage

## Goal

Persist the synchronized relationship between a camera frame and its physical
inspection position.

## Stored schema

```text
mission_id
frame_index
timestamp
distance_m
source
frame_path
```

## Prototype storage

Day 4.3 uses one JSON Lines file per mission:

```text
video/storage/
└── M-XXXX.jsonl
```

This avoids a database migration while the video pipeline is still evolving.

The storage contract is deliberately independent of the API so the prototype can
later move to PostgreSQL without changing the frame metadata schema.

## API

### Store

```text
POST /api/v1/video/frames
```

### List mission frames

```text
GET /api/v1/video/missions/{mission_id}/frames?limit=100
```

### Get one frame

```text
GET /api/v1/video/missions/{mission_id}/frames/{frame_index}
```

## Why this matters

An AI detection can later reference:

```text
mission_id
frame_index
distance_m
```

and therefore connect the visual event to telemetry graphs and the 3D inspection
map.

## Verification

Run:

```powershell
pytest -q
```

Then manually create a frame record using the POST endpoint and read it back
using the list/get endpoints.
