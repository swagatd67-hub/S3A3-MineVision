# Day 4.2 — Frame ↔ Distance Synchronization

## Goal

Attach every camera frame to the same mission and spatial coordinate system used
by robot telemetry.

Primary key:

```text
mission_id + timestamp + distance_m
```

## Camera stream

```text
frame_index
timestamp
image
```

## Telemetry stream

```text
mission_id
timestamp
distance_m
```

## Synchronization rule

When a frame timestamp is between two telemetry samples, distance is linearly
interpolated:

```text
t0 ----------- frame ----------- t1
d0 ----------- distance -------- d1
```

Frames outside the telemetry window are accepted only when the nearest sample
is within the configured maximum time gap.

## Output

```text
frame_index
timestamp
mission_id
distance_m
interpolation
source_delta_ms
```

This becomes the common spatial reference for future:

```text
video ↔ AI detection ↔ sensor graph ↔ 3D map ↔ cleaning action
```

No database migration is required for Day 4.2.
