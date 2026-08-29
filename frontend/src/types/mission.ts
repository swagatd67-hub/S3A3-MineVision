export type MissionStatus =
  | 'planned'
  | 'active'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'created'
  | 'ready'
  | 'running'
  | 'cancelled';

export interface Mission {
  mission_id: string;
  status: MissionStatus;
  robot_id?: string;
  objective?: string;
  source?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  distance_m?: number;
  notes?: string;
  location?: string;
  defectsCount?: number;
}

export interface BackendMission {
  mission_id: string;
  robot_id: string;
  objective: string;
  status: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  notes?: string | null;
}

export interface CreateMissionPayload {
  robot_id: string;
  objective?: 'INSPECT' | 'INSPECT_AND_CLEAN' | 'INSPECT_SAMPLE';
  notes?: string;
}

export interface MissionSnapshotData {
  mission_id: string;
  robot_id: string;
  objective: string;
  status: string;
  timestamps: Record<string, string | null>;
  notes?: string | null;
  progress: {
    current_distance_m: number;
    total_inspected_distance_m: number;
    observation_count: number;
    morphology_measurements_count: number;
    cleaning_operations_count: number;
    duration_sec?: number | null;
  };
  digital_twin?: Record<string, unknown> | null;
}