import { api } from './client';
import type { DigitalTwinState, MissionSnapshot } from '../types/digitalTwin';
import { extractErrorMessage } from './findings';

export class DigitalTwinApiError extends Error {
  public code: string;
  public missionId?: string;

  constructor(message: string, code: string, missionId?: string) {
    super(message);
    this.name = 'DigitalTwinApiError';
    this.code = code;
    this.missionId = missionId;
  }
}

/**
 * Fetches the Digital Twin aggregated state snapshot for a given mission.
 * API Endpoint: GET /api/v1/missions/{mission_id}/digital_twin
 */
export async function getMissionDigitalTwin(
  missionId: string
): Promise<DigitalTwinState> {
  try {
    const response = await api.get<DigitalTwinState>(
      `/api/v1/missions/${encodeURIComponent(missionId)}/digital_twin`
    );
    return response.data;
  } catch (err) {
    const message = extractErrorMessage(
      err,
      `Failed to fetch Digital Twin for mission '${missionId}'.`
    );
    throw new DigitalTwinApiError(message, 'DIGITAL_TWIN_FETCH_FAILED', missionId);
  }
}

/**
 * Fetches the unified mission snapshot combining lifecycle, progress metrics, and Digital Twin.
 * API Endpoint: GET /api/v1/missions/{mission_id}/snapshot
 */
export async function getMissionSnapshot(
  missionId: string
): Promise<MissionSnapshot> {
  try {
    const response = await api.get<MissionSnapshot>(
      `/api/v1/missions/${encodeURIComponent(missionId)}/snapshot`
    );
    return response.data;
  } catch (err) {
    const message = extractErrorMessage(
      err,
      `Failed to fetch snapshot for mission '${missionId}'.`
    );
    throw new DigitalTwinApiError(message, 'SNAPSHOT_FETCH_FAILED', missionId);
  }
}
