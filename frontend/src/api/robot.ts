import { api } from './client';
import type { RobotCommandPayload, RobotCommandResponse } from '../types/robotControl';
import { isAxiosError } from 'axios';

export async function sendRobotCommand(
  robotId: string,
  command: RobotCommandPayload,
  missionId?: string
): Promise<RobotCommandResponse> {
  try {
    const response = await api.post<RobotCommandResponse>(
      `/api/v1/robots/${encodeURIComponent(robotId)}/command`,
      command,
      {
        params: missionId ? { mission_id: missionId } : undefined,
      }
    );
    return response.data;
  } catch (error) {
    if (isAxiosError(error) && error.response?.data?.detail) {
      throw new Error(String(error.response.data.detail), { cause: error });
    }
    throw error;
  }
}

export async function sendEmergencyStop(
  robotId: string,
  missionId?: string
): Promise<RobotCommandResponse> {
  try {
    const response = await api.post<RobotCommandResponse>(
      `/api/v1/robots/${encodeURIComponent(robotId)}/estop`,
      {},
      {
        params: missionId ? { mission_id: missionId } : undefined,
      }
    );
    return response.data;
  } catch (error) {
    if (isAxiosError(error) && error.response?.data?.detail) {
      throw new Error(String(error.response.data.detail), { cause: error });
    }
    throw error;
  }
}
