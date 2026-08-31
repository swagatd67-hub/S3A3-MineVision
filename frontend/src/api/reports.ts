/**
 * API client and report aggregator for PipeVision Engineering Inspection Reports.
 * Composes GET /api/v1/missions/{id}, /snapshot, /observations, /analytics, /events, and /robots.
 */

import { api } from './client';
import { getMission } from './missions';
import { getMissionSnapshot } from './digitalTwin';
import { getMissionObservations } from './findings';
import { getMissionAnalytics, getMissionEvents } from './analytics';
import { CLASS_CODE_MAP } from './findings';
import type {
  EngineeringReport,
  PACPGradeSummary,
  ReportAnalyticsEvent,
  ReportAnalyticsSummary,
  ReportObservation,
  ReportRecommendation,
} from '../types/report';
import type { RobotInfo } from '../types/robot';

async function fetchRobotInfo(robotId: string): Promise<RobotInfo | null> {
  try {
    const res = await api.get<RobotInfo>(`/api/v1/robots/${robotId}`);
    return res.data;
  } catch {
    return null;
  }
}

function deriveClockPositionString(box: unknown): string {
  if (!box) return '12:00';
  let u1 = 0.5;
  let u2 = 0.5;
  if (Array.isArray(box)) {
    u1 = (box as number[])[1] ?? 0.5;
    u2 = (box as number[])[3] ?? 0.5;
  } else if (typeof box === 'object') {
    const b = box as { x1?: number; x2?: number; xmin?: number; xmax?: number };
    u1 = b.x1 ?? b.xmin ?? 0.5;
    u2 = b.x2 ?? b.xmax ?? 0.5;
  }
  const uCenter = (u1 + u2) / 2;
  const normU = uCenter <= 1.0 ? uCenter : uCenter / 1920;
  const hour = Math.round(normU * 12) % 12;
  const displayHour = hour === 0 ? 12 : hour;
  return `${String(displayHour).padStart(2, '0')}:00`;
}

function deriveObservationSeverity(classCode: string, confidence: number): 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' {
  const code = classCode.toUpperCase();
  if (['RB', 'PB', 'PH', 'BE', 'RO'].includes(code)) {
    return confidence >= 0.85 ? 'CRITICAL' : 'HIGH';
  }
  if (['FS', 'IS', 'CR', 'CRACK', 'CORROSION'].includes(code)) {
    return confidence >= 0.85 ? 'HIGH' : 'MEDIUM';
  }
  if (['DE', 'OB', 'AF', 'FO', 'GR', 'BLOCKAGE'].includes(code)) {
    return confidence >= 0.8 ? 'HIGH' : 'MEDIUM';
  }
  return confidence >= 0.7 ? 'MEDIUM' : 'LOW';
}

function calculateDerivedAssessment(obsList: ReportObservation[]): PACPGradeSummary {
  if (obsList.length === 0) {
    return {
      isDerived: true,
      label: 'Derived Assessment: Insufficient data',
      description: 'No observations recorded for this inspection segment to derive structural or O&M condition grades.',
      structuralGrade: null,
      omGrade: null,
      overallGradeText: 'Grade 0 - Insufficient Data',
    };
  }

  const criticalCount = obsList.filter((o) => o.severity === 'CRITICAL').length;
  const highCount = obsList.filter((o) => o.severity === 'HIGH').length;
  const mediumCount = obsList.filter((o) => o.severity === 'MEDIUM').length;

  let structuralGrade = 1;
  let omGrade = 1;

  if (criticalCount >= 2) structuralGrade = 5;
  else if (criticalCount === 1) structuralGrade = 4;
  else if (highCount >= 2) structuralGrade = 3;
  else if (highCount === 1 || mediumCount >= 2) structuralGrade = 2;

  const omDefects = obsList.filter((o) =>
    ['DE', 'OB', 'AF', 'FO', 'GR', 'BLOCKAGE'].includes(o.class_code.toUpperCase())
  );
  if (omDefects.length >= 3) omGrade = 4;
  else if (omDefects.length >= 1) omGrade = 3;

  const maxGrade = Math.max(structuralGrade, omGrade);
  let gradeText = `Derived Grade ${maxGrade} - Minor Condition`;
  if (maxGrade === 5) gradeText = `Derived Grade 5 - Significant Structural Defect`;
  else if (maxGrade === 4) gradeText = `Derived Grade 4 - Poor Pipe Condition / Severe Defect`;
  else if (maxGrade === 3) gradeText = `Derived Grade 3 - Moderate Defect Observed`;
  else if (maxGrade === 2) gradeText = `Derived Grade 2 - Minor Defect Observed`;

  return {
    isDerived: true,
    label: 'Derived Assessment',
    description: `Deterministic evaluation derived from ${obsList.length} backend observation(s) (${criticalCount} Critical, ${highCount} High, ${mediumCount} Medium). Not an official NASSCO PACP certification.`,
    structuralGrade,
    omGrade,
    overallGradeText: gradeText,
  };
}

function generateRecommendations(
  obsList: ReportObservation[],
  events: ReportAnalyticsEvent[]
): ReportRecommendation[] {
  const recommendations: ReportRecommendation[] = [];

  const hasDebrisOrOb = obsList.some((o) =>
    ['DE', 'OB', 'AF', 'GR', 'BLOCKAGE'].includes(o.class_code.toUpperCase())
  );
  if (hasDebrisOrOb) {
    recommendations.push({
      id: 'REC-001',
      title: 'High-Pressure Jetting & Cleansing',
      action: 'Schedule high-pressure sewer jetting to clear deposit and blockage accumulation detected along the pipe invert.',
      priority: 'HIGH',
      source: 'Observation Log (Debris / Deposit detected)',
    });
  }

  const hasStructural = obsList.some((o) =>
    ['RB', 'PB', 'PH', 'BE', 'RO', 'FS', 'CR'].includes(o.class_code.toUpperCase())
  );
  if (hasStructural) {
    recommendations.push({
      id: 'REC-002',
      title: 'Structural Integrity Engineering Review',
      action: 'Conduct targeted spot lining or structural rehabilitation assessment for fracture / broken pipe locations.',
      priority: 'URGENT',
      source: 'Observation Log (Structural defect detected)',
    });
  }

  const hasInfiltration = obsList.some((o) => o.class_code.toUpperCase() === 'IS');
  if (hasInfiltration) {
    recommendations.push({
      id: 'REC-003',
      title: 'Water Infiltration Sealing Review',
      action: 'Perform chemical grouting or joint seal inspection at active groundwater infiltration points.',
      priority: 'MEDIUM',
      source: 'Observation Log (Water Infiltration detected)',
    });
  }

  if (
    events.some(
      (e) => e.severity === 'critical' || e.event_type.includes('stale') || e.event_type.includes('reconnect')
    )
  ) {
    recommendations.push({
      id: 'REC-004',
      title: 'Sensor & Crawler Diagnostic',
      action: 'Inspect crawler wheel calibration and telemetry link due to cross-sensor anomaly events recorded during survey.',
      priority: 'MEDIUM',
      source: 'Analytics Events (Cross-sensor anomalies)',
    });
  }

  if (recommendations.length === 0) {
    recommendations.push({
      id: 'REC-000',
      title: 'No Action Required',
      action: 'No specific operational recommendation available based on current observation data.',
      priority: 'LOW',
      source: 'Derived Recommendation Engine',
    });
  }

  return recommendations;
}

/**
 * Fetches and composes all backend mission datasets into a single EngineeringReport object.
 */
export async function getInspectionReport(missionId: string): Promise<EngineeringReport> {
  const [missionRes, snapshotRes, obsRes, analyticsRes, eventsRes] = await Promise.allSettled([
    getMission(missionId),
    getMissionSnapshot(missionId),
    getMissionObservations(missionId),
    getMissionAnalytics(missionId),
    getMissionEvents(missionId),
  ]);

  if (missionRes.status === 'rejected' || !missionRes.value) {
    throw new Error(`Mission '${missionId}' could not be fetched from backend.`);
  }

  const mission = missionRes.value;
  const snapshot = snapshotRes.status === 'fulfilled' ? snapshotRes.value : null;
  const rawObsResponse = obsRes.status === 'fulfilled' ? obsRes.value : null;
  const rawAnalytics = analyticsRes.status === 'fulfilled' ? analyticsRes.value : null;
  const rawEvents = eventsRes.status === 'fulfilled' ? eventsRes.value : null;

  // Try fetching robot info if robot_id is present
  const robot: RobotInfo | null = mission.robot_id ? await fetchRobotInfo(mission.robot_id) : null;

  // Parse observations list
  const rawObsList =
    rawObsResponse?.observations ||
    snapshot?.digital_twin?.inspection_map?.observations ||
    snapshot?.digital_twin?.latest_observations ||
    [];

  const observations: ReportObservation[] = rawObsList.map((o) => {
    const classCode = o.class_code || 'UNKNOWN';
    const className = CLASS_CODE_MAP[classCode.toUpperCase()] || classCode;
    const confidence = typeof o.confidence === 'number' ? o.confidence : 0;
    return {
      observation_id: o.observation_id,
      frame_index: o.frame_index,
      timestamp: o.timestamp ?? null,
      distance_m: o.distance_m ?? 0,
      class_code: classCode,
      class_name: className,
      confidence,
      localization_quality: o.localization_quality || 'UNKNOWN',
      box: o.box as ReportObservation['box'],
      clock_position: deriveClockPositionString(o.box),
      severity: deriveObservationSeverity(classCode, confidence),
    };
  });

  // Parse analytics summary & events
  const parsedEvents: ReportAnalyticsEvent[] = Array.isArray(rawEvents?.events)
    ? rawEvents.events.map((e, index) => ({
        event_id: `EVT-${index + 1}`,
        event_type: e.event_type || 'anomaly',
        distance_m: e.distance_start_m || 0,
        severity: e.severity || 'info',
        description: e.explanation || e.recommendation || '',
      }))
    : [];

  const analytics: ReportAnalyticsSummary | null = rawAnalytics
    ? {
        total_distance_m: rawAnalytics.distance?.change_m ?? null,
        avg_speed_m_s: null,
        max_speed_m_s: null,
        duration_sec: rawAnalytics.duration_s ?? null,
        battery_used_percent: null,
        stale_packets_dropped: null,
        events: parsedEvents,
      }
    : null;

  // Determine inspected distance
  const inspectedDistanceM =
    snapshot?.progress?.total_inspected_distance_m ??
    analytics?.total_distance_m ??
    (observations.length > 0 ? Math.max(...observations.map((o) => o.distance_m)) : 0);

  // Status & Title
  const statusUpper = (mission.status || 'UNKNOWN').toUpperCase();
  const isInterim = statusUpper === 'RUNNING' || statusUpper === 'PAUSED';
  const reportTitle = isInterim ? 'INTERIM INSPECTION REPORT' : 'FINAL INSPECTION REPORT';

  // Dates
  const surveyDateRaw = mission.completed_at || mission.created_at || new Date().toISOString();
  const surveyDate = surveyDateRaw.split('T')[0] ?? surveyDateRaw;
  const createdDate = (mission.created_at || '').split('T')[0] ?? '';
  const completedDate = mission.completed_at ? mission.completed_at.split('T')[0] ?? null : null;

  // Derived Assessment & Recommendations
  const derivedAssessment = calculateDerivedAssessment(observations);
  const recommendations = generateRecommendations(observations, parsedEvents);

  return {
    missionId: mission.mission_id,
    status: statusUpper,
    reportTitle,
    isInterim,
    surveyDate,
    createdDate,
    completedDate,
    objective: mission.objective || 'Pipeline Inspection Survey',
    notes: mission.notes ?? null,

    inspectedDistanceM,
    totalObservationsCount: observations.length,

    robotId: mission.robot_id || 'Not available',
    robot,
    inspectorName: 'Not available',
    clientName: 'Not available',
    assetCode: mission.objective ? `ASSET-${mission.objective.replace(/\s+/g, '-').toUpperCase()}` : 'Not available',
    pipeSegment: mission.notes ? mission.notes : 'Not available',

    observations,
    analytics,

    derivedAssessment,
    recommendations,
  };
}
