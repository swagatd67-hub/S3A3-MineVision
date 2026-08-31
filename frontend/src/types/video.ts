export interface Frame {
  mission_id: string;
  frame_index: number;
  timestamp: string;
  distance_m: number;
  source: string;
  frame_path: string | null;
}

export type FrameMetadata = Frame;

export interface SnapshotRecord {
  snapshot_id: string;
  mission_id: string;
  frame_index: number;
  timestamp: string | null;
  distance_m: number | null;
  camera_id: string | null;
  image_url: string;
  notes: string | null;
  created_at: string;
}

export interface CreateSnapshotRequest {
  frame_index: number;
  camera_id?: string | null;
  notes?: string | null;
}

export type RecordingStatus = "RECORDING" | "STOPPED";

export interface RecordingSession {
  recording_id: string;
  mission_id: string;
  camera_id: string | null;
  start_time: string;
  stop_time: string | null;
  status: RecordingStatus;
  frame_count: number;
  media_location: string | null;
}

export interface RecordingStatusResponse {
  mission_id: string;
  is_recording: boolean;
  session: RecordingSession | null;
}

export interface Detection {
  class_name: string;
  confidence: number;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
}

export interface DetectionResult {
  mission_id: string;
  frame_index: number;
  timestamp: string;
  distance_m: number;
  source: string;
  model: string;
  image_width: number;
  image_height: number;
  inference_ms: number | null;
  detections: Detection[];
}