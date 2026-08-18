export type MissionStatus =
  | "planned"
  | "active"
  | "paused"
  | "completed"
  | "failed";

export interface Mission {
  mission_id: string;
  status: MissionStatus;
  source?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  distance_m?: number;
}