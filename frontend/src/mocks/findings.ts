import type { InspectionFinding } from "../types/finding";

export const mockFindings: InspectionFinding[] = [
  {
    mission_id: "M-DAY5-DEMO",
    frame_index: 421,
    timestamp: "2026-08-18T11:48:21.120Z",
    distance_m: 18.7,
    defect: "Crack",
    confidence: 0.91,
    severity: "high",
  },
  {
    mission_id: "M-DAY5-DEMO",
    frame_index: 448,
    timestamp: "2026-08-18T11:48:32.040Z",
    distance_m: 24.2,
    defect: "Attached Deposit",
    confidence: 0.82,
    severity: "medium",
  },
  {
    mission_id: "M-DAY5-DEMO",
    frame_index: 503,
    timestamp: "2026-08-18T11:48:54.320Z",
    distance_m: 31.8,
    defect: "Obstacle",
    confidence: 0.89,
    severity: "critical",
  },
];