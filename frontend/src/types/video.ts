export interface Frame {
  mission_id: string;
  frame_index: number;
  timestamp: string;
  distance_m: number;
  source: string;
  frame_path: string | null;
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