import { isAxiosError } from 'axios';
import { api } from './client';
import type {
  Mission,
  BackendMission,
  CreateMissionPayload,
  MissionSnapshotData,
  MissionStatus,
} from '../types/mission';

/**
 * Normalizes a backend mission DTO into the UI Mission model.
 */
export function normalizeMission(bm: BackendMission): Mission {
  const rawStatus = (bm.status || '').toUpperCase();
  let normalizedStatus: MissionStatus = 'planned';

  if (rawStatus === 'RUNNING' || rawStatus === 'ACTIVE') {
    normalizedStatus = 'active';
  } else if (rawStatus === 'COMPLETED') {
    normalizedStatus = 'completed';
  } else if (rawStatus === 'PAUSED') {
    normalizedStatus = 'paused';
  } else if (rawStatus === 'FAILED' || rawStatus === 'CANCELLED') {
    normalizedStatus = 'failed';
  }

  const robotLabel = bm.robot_id ? `Robot ${bm.robot_id}` : 'ROV-01';
  const locationLabel = bm.notes && bm.notes.trim().length > 0
    ? bm.notes
    : `${robotLabel} • ${bm.objective || 'INSPECT'} Survey`;

  return {
    mission_id: bm.mission_id,
    robot_id: bm.robot_id,
    objective: bm.objective,
    status: normalizedStatus,
    source: bm.robot_id || 'ROV-01 (Tactical)',
    created_at: bm.created_at,
    started_at: bm.started_at ?? undefined,
    completed_at: bm.completed_at ?? undefined,
    notes: bm.notes ?? undefined,
    location: locationLabel,
    distance_m: 0,
    defectsCount: 0,
  };
}

/**
 * Helper to extract descriptive error messages from backend Axios HTTP responses.
 */
export function extractErrorMessage(err: unknown, fallback: string): string {
  if (isAxiosError(err) && err.response?.data?.detail) {
    const detail = err.response.data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0 && detail[0]?.msg) {
      return detail[0].msg;
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}

/**
 * GET /api/v1/missions
 */
export async function listMissions(): Promise<Mission[]> {
  try {
    const response = await api.get<BackendMission[]>('/api/v1/missions');
    return response.data.map(normalizeMission);
  } catch (err) {
    throw new Error(extractErrorMessage(err, 'Failed to list missions from backend.'), { cause: err });
  }
}

/**
 * GET /api/v1/missions/{id}
 */
export async function getMission(missionId: string): Promise<Mission> {
  try {
    const response = await api.get<BackendMission>(`/api/v1/missions/${missionId}`);
    return normalizeMission(response.data);
  } catch (err) {
    throw new Error(extractErrorMessage(err, `Failed to fetch mission '${missionId}'.`), { cause: err });
  }
}

/**
 * POST /api/v1/missions
 * Directly calls backend POST /api/v1/missions using registered robot IDs (e.g. ROV-01).
 * Does not perform hidden automatic robot registration.
 */
export async function createMission(payload: CreateMissionPayload): Promise<Mission> {
  const robotId = payload.robot_id || 'ROV-01';

  try {
    const response = await api.post<BackendMission>('/api/v1/missions', {
      robot_id: robotId,
      objective: payload.objective || 'INSPECT',
      notes: payload.notes || undefined,
    });
    return normalizeMission(response.data);
  } catch (err) {
    if (isAxiosError(err) && err.response?.status === 404) {
      const detail = err.response.data?.detail;
      if (typeof detail === 'string' && detail.toLowerCase().includes('robot not registered')) {
        throw new Error(`Robot '${robotId}' is not registered in the system.`, { cause: err });
      }
    }
    throw new Error(extractErrorMessage(err, 'Failed to create mission in backend.'), { cause: err });
  }
}

/**
 * POST /api/v1/missions/{id}/start
 */
export async function startMission(missionId: string): Promise<Mission> {
  try {
    const response = await api.post<BackendMission>(`/api/v1/missions/${missionId}/start`);
    return normalizeMission(response.data);
  } catch (err) {
    throw new Error(extractErrorMessage(err, `Failed to start mission '${missionId}'.`), { cause: err });
  }
}

/**
 * POST /api/v1/missions/{id}/pause
 */
export async function pauseMission(missionId: string): Promise<Mission> {
  try {
    const response = await api.post<BackendMission>(`/api/v1/missions/${missionId}/pause`);
    return normalizeMission(response.data);
  } catch (err) {
    throw new Error(extractErrorMessage(err, `Failed to pause mission '${missionId}'.`), { cause: err });
  }
}

/**
 * POST /api/v1/missions/{id}/resume
 */
export async function resumeMission(missionId: string): Promise<Mission> {
  try {
    const response = await api.post<BackendMission>(`/api/v1/missions/${missionId}/resume`);
    return normalizeMission(response.data);
  } catch (err) {
    throw new Error(extractErrorMessage(err, `Failed to resume mission '${missionId}'.`), { cause: err });
  }
}

/**
 * POST /api/v1/missions/{id}/complete
 */
export async function completeMission(missionId: string): Promise<Mission> {
  try {
    const response = await api.post<BackendMission>(`/api/v1/missions/${missionId}/complete`);
    return normalizeMission(response.data);
  } catch (err) {
    throw new Error(extractErrorMessage(err, `Failed to complete mission '${missionId}'.`), { cause: err });
  }
}

/**
 * POST /api/v1/missions/{id}/cancel
 */
export async function cancelMission(missionId: string): Promise<Mission> {
  try {
    const response = await api.post<BackendMission>(`/api/v1/missions/${missionId}/cancel`);
    return normalizeMission(response.data);
  } catch (err) {
    throw new Error(extractErrorMessage(err, `Failed to cancel mission '${missionId}'.`), { cause: err });
  }
}

/**
 * GET /api/v1/missions/{id}/snapshot
 */
export async function getMissionSnapshot(missionId: string): Promise<MissionSnapshotData> {
  try {
    const response = await api.get<MissionSnapshotData>(`/api/v1/missions/${missionId}/snapshot`);
    return response.data;
  } catch (err) {
    throw new Error(extractErrorMessage(err, `Failed to fetch snapshot for mission '${missionId}'.`), { cause: err });
  }
}
