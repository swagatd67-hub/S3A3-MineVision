export type WebSocketConnectionStatus =
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'DISCONNECTED'
  | 'ERROR';

export interface TelemetryIMU {
  ax: number;
  ay: number;
  az: number;
  gx: number;
  gy: number;
  gz: number;
  temperature_c?: number | null;
}

export interface TelemetryPressure {
  body_kpa?: number | null;
  front_anchor_kpa?: number | null;
  rear_anchor_kpa?: number | null;
}

export interface TelemetryWater {
  temperature_c?: number | null;
  ph?: number | null;
  conductivity_ms_cm?: number | null;
  turbidity_ntu?: number | null;
}

export interface TelemetryData {
  robot_id: string;
  mission_id?: string | null;
  timestamp?: string | null;
  battery_percent?: number | null;
  distance_m?: number | null;
  body_diameter_mm?: number | null;
  state: string;
  imu?: TelemetryIMU | null;
  pressure?: TelemetryPressure | null;
  water?: TelemetryWater | null;
}

export interface TelemetryEvent {
  type: 'telemetry';
  data: TelemetryData;
}

export interface AnalyticsMetricPoint {
  metric: string;
  distance_m: number | null;
  timestamp: string;
  value: number;
  unit: string;
}

export interface AnalyticsUpdateEvent {
  type: 'analytics_update';
  mission_id: string;
  distance_m?: number | null;
  timestamp: string;
  latest_points: Record<string, AnalyticsMetricPoint>;
  recent_events: unknown[];
  new_event?: unknown | null;
}

export type IncomingWebSocketMessage = TelemetryEvent | AnalyticsUpdateEvent;
