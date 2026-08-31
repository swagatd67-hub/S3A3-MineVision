/**
 * Strict TypeScript interfaces for PipeVision Engineering Inspection Report.
 * Maps real backend data from Mission, MissionSnapshot, InspectionObservation,
 * Analytics, CrossSensorEvents, and Robot models.
 */

import type { BoundingBox } from './digitalTwin';
import type { RobotInfo } from './robot';

export interface ReportObservation {
  observation_id: string;
  frame_index: number;
  timestamp: string | null;
  distance_m: number;
  class_code: string;
  class_name: string;
  confidence: number;
  localization_quality: string;
  box: BoundingBox | { xmin?: number; ymin?: number; xmax?: number; ymax?: number } | number[] | null;
  clock_position: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

export interface ReportAnalyticsEvent {
  event_id: string;
  event_type: string;
  distance_m: number;
  severity: string;
  description: string;
}

export interface ReportAnalyticsSummary {
  total_distance_m: number | null;
  avg_speed_m_s: number | null;
  max_speed_m_s: number | null;
  duration_sec: number | null;
  battery_used_percent: number | null;
  stale_packets_dropped: number | null;
  events: ReportAnalyticsEvent[];
}

export interface PACPGradeSummary {
  isDerived: boolean;
  label: string;
  description: string;
  structuralGrade: number | null; // 1-5
  omGrade: number | null; // 1-5
  overallGradeText: string;
}

export interface ReportRecommendation {
  id: string;
  title: string;
  action: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
  source: string;
}

export interface EngineeringReport {
  missionId: string;
  status: string;
  reportTitle: string;
  isInterim: boolean;
  surveyDate: string;
  createdDate: string;
  completedDate: string | null;
  objective: string;
  notes: string | null;

  // Pipe & Inspection Metrics
  inspectedDistanceM: number;
  totalObservationsCount: number;

  // Robot / Asset Metadata
  robotId: string;
  robot: RobotInfo | null;
  inspectorName: string; // "Not available"
  clientName: string; // "Not available"
  assetCode: string; // Derived or "Not available"
  pipeSegment: string; // Derived or "Not available"

  // Real Observations & Analytics
  observations: ReportObservation[];
  analytics: ReportAnalyticsSummary | null;

  // Derived Assessment & Recommendations
  derivedAssessment: PACPGradeSummary;
  recommendations: ReportRecommendation[];
}
