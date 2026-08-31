export interface AnalyticsTelemetryPoint {
  timestamp: string;
  value: number;
}

export interface AnalyticsMetricExplanation {
  metric: string;
  trend: 'stable' | 'increasing' | 'decreasing' | 'insufficient_data' | 'no_data';
  start?: number | null;
  end?: number | null;
  change?: number | null;
  unit: string;
  severity: 'info' | 'warning' | 'critical';
  explanation: string;
  recommendation: string;
}

export interface AnalyticsAnomalyPoint {
  timestamp: string;
  value: number;
  z_score: number;
}

export interface MissionAnalyticsResponse {
  mission_id?: string;
  robot_id?: string;
  mission_status?: string;
  objective?: string | null;
  sample_count: number;
  start_time?: string | null;
  end_time?: string | null;
  duration_s: number;
  distance: {
    start_m: number | null;
    end_m: number | null;
    change_m: number;
  };
  latest_state?: string | null;
  series: Record<string, AnalyticsTelemetryPoint[]>;
  explanations: AnalyticsMetricExplanation[];
  anomalies: Record<string, AnalyticsAnomalyPoint[]>;
  error?: string;
}

export interface ChartPoint {
  distance_m: number;
  timestamp: string;
  value: number;
}

export interface MissionChartSeries {
  metric: string;
  label: string;
  unit: string;
  x_axis: {
    field: string;
    label: string;
    unit: string;
  };
  y_axis: {
    field: string;
    label: string;
    unit: string;
  };
  points: ChartPoint[];
}

export interface MissionChartsResponse {
  mission_id?: string;
  robot_id?: string;
  mission_status?: string;
  objective?: string | null;
  chart_count: number;
  charts: Record<string, MissionChartSeries>;
  timeline?: Array<{
    distance_m: number;
    timestamp: string;
    state: string;
  }>;
  error?: string;
}

export interface CrossSensorEvent {
  event_type: string;
  distance_start_m: number;
  distance_end_m: number;
  severity: 'info' | 'warning' | 'critical';
  evidence: string[];
  explanation: string;
  recommendation: string;
}

export interface MissionEventsResponse {
  mission_id?: string;
  robot_id?: string;
  event_count: number;
  events: CrossSensorEvent[];
  error?: string;
}
