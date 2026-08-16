# Day 3 — Telemetry Intelligence

## Goal

Turn persisted and live robot telemetry into mission-scoped, distance-indexed
inspection intelligence.

Day 3 builds the analytics layer that connects:

- telemetry
- mission context
- graphs
- anomaly screening
- cross-sensor events
- real-time WebSocket analytics

The backend owns data preparation and explainable analytics so the frontend
does not need to reconstruct sensor logic.

---

# 3.1 Analytics Foundation

## Endpoint

```text
GET /api/v1/analytics/telemetry/{robot_id}?limit=500