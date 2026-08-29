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

export interface BackendObservation {
  observation_id: string;
  frame_index: number;
  timestamp: string | null;
  distance_m: number | null;
  class_code: string;
  confidence: number;
  localization_quality?: string | null;
  model_name?: string | null;
  model_version?: string | null;
  box?: { ymin?: number; xmin?: number; ymax?: number; xmax?: number } | number[] | null;
}

export interface BackendObservationsResponse {
  mission_id: string;
  count: number;
  observations: BackendObservation[];
}

export interface ExtendedFinding {
  id: string;
  observation_id: string;
  mission_id: string;
  frame_index: number;
  timestamp: string;
  distance_m: number;
  defect: string;
  class_code: string;
  confidence: number;
  severity: FindingSeverity;
  status: 'UNRESOLVED' | 'IN_REVIEW' | 'RESOLVED';
  clockPosition: string;
  notes: string[];
  image_url?: string;
}