export type FindingSeverity =
  | "low"
  | "medium"
  | "high"
  | "critical";

export interface InspectionFinding {
  mission_id: string;
  frame_index: number;
  timestamp: string;
  distance_m: number;
  defect: string;
  confidence: number;
  severity?: FindingSeverity;
  image_url?: string;
}