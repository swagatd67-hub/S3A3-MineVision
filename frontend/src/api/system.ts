import { api } from './client';

export type RuntimeMode = 'SIMULATOR' | 'HARDWARE' | 'UNKNOWN';

export interface BackendHealth {
  status: string;
  runtime_mode?: 'SIMULATOR' | 'HARDWARE';
  environment?: string;
}

export async function getBackendHealth(): Promise<BackendHealth> {
  const response = await api.get<BackendHealth>('/health');
  return response.data;
}
