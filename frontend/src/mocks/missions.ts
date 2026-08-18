import type { Mission } from "../types/mission";

export const mockMissions: Mission[] = [
  {
    mission_id: "M-DAY5-DEMO",
    status: "active",
    source: "robot-01",
    created_at: "2026-08-18T11:30:00Z",
    started_at: "2026-08-18T11:42:00Z",
    distance_m: 126.4,
  },
  {
    mission_id: "M-DAY4-TEST",
    status: "completed",
    source: "webcam",
    created_at: "2026-08-17T07:30:00Z",
    started_at: "2026-08-17T07:45:00Z",
    completed_at: "2026-08-17T08:05:00Z",
    distance_m: 42.8,
  },
  {
    mission_id: "M-DEMO-003",
    status: "planned",
    source: "robot-02",
    created_at: "2026-08-18T14:20:00Z",
    distance_m: 0,
  },
];