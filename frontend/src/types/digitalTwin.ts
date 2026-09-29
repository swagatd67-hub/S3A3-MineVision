/**
 * TypeScript Interfaces for PipeVision Digital Twin and Mission Snapshot.
 * Matches backend schemas from digital_twin/models.py, mapping/models.py,
 * morphology/models.py, and backend/app/services/mission/models.py.
 */

export type SynchronizationStatus =
  | 'INITIALIZING'
  | 'SYNCHRONIZED'
  | 'DEGRADED'
  | 'STALE'
  | 'INVALID';

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface MapObservationProvenance {
  model_name: string;
  model_version: string;
  source_type: string;
}

export interface MapObservationCoordinates {
  x: number;
  y: number;
}

export interface MapObservation {
  observation_id: string;
  mission_id?: string;
  frame_index: number;
  timestamp?: string | null;
  distance_m: number;
  coordinates?: MapObservationCoordinates;
  heading_deg?: number | null;
  class_code: string;
  confidence: number;
  threshold?: number | null;
  box?: BoundingBox | { xmin?: number; ymin?: number; xmax?: number; ymax?: number } | number[] | null;
  localization_quality?: string;
  provenance?: MapObservationProvenance;
}

export interface PipeInspectionMapSummary {
  total_inspected_distance_m: number;
  start_distance_m: number | null;
  end_distance_m: number | null;
  observation_count: number;
}

export interface PipeInspectionMap {
  mission_id: string;
  summary: PipeInspectionMapSummary;
  observations: MapObservation[];
}

export interface MorphologyObservationProvenance {
  source: string;
  calibration_mode: string;
}

export interface MorphologyObservation {
  observation_id: string;
  mission_id: string;
  frame_index: number;
  timestamp: string | null;
  distance_m: number;
  robot_body_diameter_mm: number | null;
  measured_pipe_diameter_mm: number | null;
  estimated_pipe_diameter_mm: number | null;
  effective_pipe_diameter_mm: number | null;
  baseline_pipe_diameter_mm: number | null;
  deformation_percent: number | null;
  pixel_span_px: number | null;
  quality: string;
  provenance: MorphologyObservationProvenance;
}

export interface MorphologyMetrics {
  total_observations: number;
  measured_count: number;
  estimated_count: number;
  unavailable_count: number;
  invalid_count: number;
  min_observed_diameter_mm: number | null;
  max_observed_diameter_mm: number | null;
  mean_observed_diameter_mm: number | null;
  max_deformation_percent: number | null;
  mean_deformation_percent: number | null;
}

export interface MorphologySummaryReport {
  mission_id: string;
  metrics: MorphologyMetrics;
  observations: MorphologyObservation[];
}

export interface DigitalTwinRobotPose {
  x: number;
  y: number;
  heading_deg: number;
  quality: string;
}

export interface DigitalTwinRobotTelemetry {
  robot_id: string;
  mission_id: string;
  timestamp: string | null;
  battery_percent: number | null;
  distance_m: number;
  body_diameter_mm: number | null;
  state: string;
}

export interface DigitalTwinRobotState {
  robot_id: string;
  operational_state: string;
  battery_percent: number | null;
  distance_m: number;
  body_diameter_mm: number | null;
  pose: DigitalTwinRobotPose | null;
  telemetry_timestamp: string | null;
  telemetry_freshness_sec: number | null;
  telemetry: DigitalTwinRobotTelemetry | null;
}

export interface DigitalTwinMissionState {
  mission_id: string;
  current_distance_m: number;
  total_inspected_distance_m: number;
  start_distance_m: number | null;
  end_distance_m: number | null;
  observation_count: number;
}

export interface DigitalTwinSystem {
  robot_id: string;
  mission_id: string;
  last_updated_at: string;
  synchronization_status: SynchronizationStatus;
  synchronization_notes: string[];
}

export interface DigitalTwinCleaningState {
  active_operation: {
    operation_id: string;
    mission_id: string;
    mode: string;
    status: string;
  } | null;
  latest_effectiveness: {
    operation_id: string;
    score: number;
  } | null;
}

export interface DigitalTwinState {
  system: DigitalTwinSystem;
  robot: DigitalTwinRobotState | null;
  mission: DigitalTwinMissionState | null;
  latest_observations: MapObservation[];
  inspection_map: PipeInspectionMap | null;
  morphology_summary: MorphologySummaryReport | null;
  cleaning: DigitalTwinCleaningState;
}

export interface MissionProgressMetrics {
  current_distance_m: number;
  total_inspected_distance_m: number;
  observation_count: number;
  morphology_measurements_count: number;
  cleaning_operations_count: number;
  duration_sec: number | null;
}

export interface MissionSnapshotTimestamps {
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface MissionSnapshot {
  mission_id: string;
  robot_id: string;
  objective: string;
  status: string;
  timestamps: MissionSnapshotTimestamps;
  notes: string | null;
  progress: MissionProgressMetrics;
  digital_twin: DigitalTwinState | null;
}

export interface ReconstructionDefect {
  id: string;
  class_code: string;
  distance_m: number;
  clock_position: string;
  clock_angle_deg: number;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence: number;
  frame_index?: number | null;
  box?: BoundingBox | Record<string, number> | null;
}

export interface ReconstructionSection {
  section_index: number;
  start_distance_m: number;
  end_distance_m: number;
  status: 'PENDING' | 'RECONSTRUCTED' | 'ANOMALOUS';
  outer_radius_mm: number;
  inner_radius_mm: number;
  defect_count: number;
}

export interface CenterlinePoint {
  x: number;
  y: number;
  z: number;
}

export interface Reconstruction3DOutput {
  mission_id: string;
  robot_id: string;
  status: string;
  total_length_m: number;
  reconstructed_length_m: number;
  progress_percent: number;
  diameter_mm: number;
  section_count: number;
  sections: ReconstructionSection[];
  centerline: CenterlinePoint[];
  defects: ReconstructionDefect[];
  generated_at: string;
  version: string;
}

