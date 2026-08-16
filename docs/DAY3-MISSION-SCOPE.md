# Day 3.2 — Mission-scoped telemetry

A robot can perform many inspections. Analytics must never mix telemetry from separate inspections.

## Flow
```text
Robot
  ↓
Mission M-001
  ↓
Telemetry(mission_id=M-001)
  ↓
Analytics
  ↓
Graphs / AI / map / report
```

Existing telemetry is retained with `mission_id = NULL` as legacy data. New simulator and robot telemetry should carry a mission id.

Run:
```powershell
python scripts\migrate_day3_mission_scope.py
```

New endpoints:
- `POST /api/v1/missions`
- `POST /api/v1/missions/{mission_id}/start`
- `POST /api/v1/missions/{mission_id}/complete`
- `GET /api/v1/telemetry/mission/{mission_id}`
- `GET /api/v1/analytics/missions/{mission_id}`

The old robot-wide analytics endpoint remains temporarily for backward compatibility.
