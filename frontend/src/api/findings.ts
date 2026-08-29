import { isAxiosError } from 'axios';
import { api } from './client';
import type {
  BackendObservation,
  BackendObservationsResponse,
  ExtendedFinding,
  FindingSeverity,
} from '../types/finding';

/**
 * Sewer-ML and repository observation class codes mapped to human-readable UI defect labels.
 */
export const CLASS_CODE_MAP: Record<string, string> = {
  // Sewer-ML standard 17 defect classes
  RB: 'Broken Pipe',
  OB: 'Pipe Obstacle',
  PF: 'Joint Fault',
  DE: 'Debris / Deposit',
  FS: 'Surface Fracture',
  IS: 'Water Infiltration',
  RO: 'Root Intrusion',
  IN: 'Lateral Connection',
  AF: 'Attached Deposit',
  BE: 'Pipe Deformation',
  FO: 'Foreign Object',
  GR: 'Grease / Fat Accumulation',
  PH: 'Pipe Hole',
  PB: 'Pipe Structural Burst',
  OS: 'Surface Damage',
  OP: 'Open Joint',
  OK: 'Intact / No Defect',

  // Additional repository & domain aliases
  CR: 'Longitudinal Crack',
  BA: 'Attached Deposit',
  CRACK: 'Pipe Crack',
  CORROSION: 'Pipe Corrosion',
  BLOCKAGE: 'Pipe Blockage',
  DEBRIS: 'Debris Deposit',
  SEDIMENT: 'Sediment Accumulation',
  STRUCTURAL_DAMAGE: 'Structural Damage',
};

/**
 * Extracts a human-readable error message from an unknown API catch reason.
 */
export function extractErrorMessage(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    if (err.response?.data?.detail) {
      if (typeof err.response.data.detail === 'string') {
        return err.response.data.detail;
      }
      return JSON.stringify(err.response.data.detail);
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}

/**
 * Deterministically derives UI severity classification from observation class code and AI confidence.
 */
export function deriveSeverity(classCode: string, confidence: number): FindingSeverity {
  const code = (classCode || '').toUpperCase();

  // Critical defect classes
  if (['PB', 'RB', 'PH', 'BE', 'STRUCTURAL_DAMAGE'].includes(code)) {
    return confidence >= 0.7 ? 'critical' : 'high';
  }

  // High defect classes
  if (['CR', 'IS', 'RO', 'OB', 'FO', 'CRACK', 'CORROSION', 'BLOCKAGE'].includes(code)) {
    return confidence >= 0.8 ? 'high' : 'medium';
  }

  // Medium defect classes
  if (['DE', 'FS', 'AF', 'GR', 'OP', 'PF', 'BA', 'DEBRIS', 'SEDIMENT'].includes(code)) {
    return confidence >= 0.8 ? 'medium' : 'low';
  }

  // Low / Intact classes
  if (['IN', 'OS', 'OK'].includes(code)) {
    return 'low';
  }

  // Fallback for unknown / unclassified class codes based on confidence score
  if (confidence >= 0.9) return 'critical';
  if (confidence >= 0.75) return 'high';
  if (confidence >= 0.5) return 'medium';
  return 'low';
}

/**
 * Derives clock position from 2D bounding box coordinates (if present) or defaults to 12:00.
 */
export function deriveClockPosition(box?: BackendObservation['box']): string {
  if (!box) return '12:00';
  let coords: [number, number, number, number] | null = null;

  if (Array.isArray(box) && box.length === 4) {
    coords = [box[0], box[1], box[2], box[3]];
  } else if (typeof box === 'object' && box !== null && 'ymin' in box) {
    const b = box as { ymin?: number; xmin?: number; ymax?: number; xmax?: number };
    coords = [b.ymin ?? 0, b.xmin ?? 0, b.ymax ?? 1, b.xmax ?? 1];
  }

  if (!coords) return '12:00';

  const [ymin, xmin, ymax, xmax] = coords;
  const cx = (xmin + xmax) / 2 - 0.5;
  const cy = (ymin + ymax) / 2 - 0.5;

  if (Math.abs(cx) < 0.1 && Math.abs(cy) < 0.1) return '12:00';

  let angleDeg = Math.atan2(cx, -cy) * (180 / Math.PI);
  if (angleDeg < 0) angleDeg += 360;

  const hour = Math.round(angleDeg / 30) % 12 || 12;
  const hourStr = hour < 10 ? `0${hour}` : `${hour}`;
  return `${hourStr}:00`;
}

/**
 * Normalizes a raw backend observation into an ExtendedFinding for the Findings UI.
 */
export function normalizeObservation(
  obs: BackendObservation,
  index: number,
  missionId: string,
  clientLocalStatus?: 'UNRESOLVED' | 'IN_REVIEW' | 'RESOLVED',
  clientLocalNotes?: string[]
): ExtendedFinding {
  const rawCode = (obs.class_code || '').toUpperCase();
  const defectLabel = CLASS_CODE_MAP[rawCode] || obs.class_code || 'Unknown / Unclassified';
  const severity = deriveSeverity(obs.class_code, obs.confidence);
  const clockPosition = deriveClockPosition(obs.box);

  const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
  const imageUrl =
    obs.frame_index !== undefined && obs.frame_index !== null
      ? `${apiBase}/api/v1/video/missions/${encodeURIComponent(missionId)}/frames/${obs.frame_index}/image`
      : undefined;

  return {
    id: obs.observation_id || `OBS-${101 + index}`,
    observation_id: obs.observation_id || `OBS-${101 + index}`,
    mission_id: missionId,
    frame_index: obs.frame_index ?? 0,
    timestamp: obs.timestamp || new Date().toISOString(),
    distance_m: obs.distance_m ?? 0.0,
    defect: defectLabel,
    class_code: obs.class_code || 'UNKNOWN',
    confidence: obs.confidence ?? 0.0,
    severity,
    status: clientLocalStatus || 'UNRESOLVED',
    clockPosition,
    notes: clientLocalNotes || [],
    image_url: imageUrl,
  };
}

/**
 * Fetches all inspection observations for a specific mission from the backend API.
 */
export async function getMissionObservations(
  missionId: string
): Promise<BackendObservationsResponse> {
  try {
    const response = await api.get<BackendObservationsResponse>(
      `/api/v1/missions/${encodeURIComponent(missionId)}/observations`
    );
    return response.data;
  } catch (err) {
    const message = extractErrorMessage(
      err,
      `Failed to fetch observations for mission '${missionId}' from backend API.`
    );
    throw new Error(message, { cause: err });
  }
}
