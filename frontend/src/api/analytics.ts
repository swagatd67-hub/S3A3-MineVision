import { api } from './client';
import type {
  MissionAnalyticsResponse,
  MissionChartsResponse,
  MissionEventsResponse,
} from '../types/analytics';
import { extractErrorMessage } from './findings';

/**
 * Custom error class for application-level API errors returned with HTTP 200 (e.g. mission_not_found).
 */
export class AnalyticsApiError extends Error {
  public code: string;
  public missionId?: string;

  constructor(message: string, code: string, missionId?: string) {
    super(message);
    this.name = 'AnalyticsApiError';
    this.code = code;
    this.missionId = missionId;
  }
}

/**
 * Fetches mission telemetry analytics summary.
 * Throws AnalyticsApiError if backend returns HTTP 200 with error property.
 */
export async function getMissionAnalytics(
  missionId: string
): Promise<MissionAnalyticsResponse> {
  try {
    const response = await api.get<MissionAnalyticsResponse>(
      `/api/v1/analytics/missions/${encodeURIComponent(missionId)}`
    );

    if (response.data && response.data.error) {
      throw new AnalyticsApiError(
        `Mission '${missionId}' not found in analytics database.`,
        response.data.error,
        missionId
      );
    }

    return response.data;
  } catch (err) {
    if (err instanceof AnalyticsApiError) {
      throw err;
    }
    const message = extractErrorMessage(
      err,
      `Failed to fetch analytics for mission '${missionId}'.`
    );
    throw new Error(message, { cause: err });
  }
}

/**
 * Fetches distance-indexed charts for a mission.
 */
export async function getMissionCharts(
  missionId: string,
  includeTimeline = true
): Promise<MissionChartsResponse> {
  try {
    const response = await api.get<MissionChartsResponse>(
      `/api/v1/analytics/missions/${encodeURIComponent(missionId)}/charts`,
      {
        params: { include_timeline: includeTimeline },
      }
    );

    if (response.data && response.data.error) {
      throw new AnalyticsApiError(
        `Charts for mission '${missionId}' not found.`,
        response.data.error,
        missionId
      );
    }

    return response.data;
  } catch (err) {
    if (err instanceof AnalyticsApiError) {
      throw err;
    }
    const message = extractErrorMessage(
      err,
      `Failed to fetch charts for mission '${missionId}'.`
    );
    throw new Error(message, { cause: err });
  }
}

/**
 * Fetches distance-merged cross-sensor screening events for a mission.
 */
export async function getMissionEvents(
  missionId: string,
  minSeverity = 'info'
): Promise<MissionEventsResponse> {
  try {
    const response = await api.get<MissionEventsResponse>(
      `/api/v1/analytics/missions/${encodeURIComponent(missionId)}/events`,
      {
        params: { min_severity: minSeverity },
      }
    );

    if (response.data && response.data.error) {
      throw new AnalyticsApiError(
        `Events for mission '${missionId}' not found.`,
        response.data.error,
        missionId
      );
    }

    return response.data;
  } catch (err) {
    if (err instanceof AnalyticsApiError) {
      throw err;
    }
    const message = extractErrorMessage(
      err,
      `Failed to fetch events for mission '${missionId}'.`
    );
    throw new Error(message, { cause: err });
  }
}
