import { api } from "./client";
import type {
  DetectionResult,
  Frame,
  FrameMetadata,
  SnapshotRecord,
  RecordingSession,
  RecordingStatusResponse,
} from "../types/video";

function getBaseUrl(): string {
  return (
    import.meta.env.VITE_API_BASE_URL ??
    "http://127.0.0.1:8000"
  );
}

export function getLiveStreamUrl(
  missionId: string,
  fps = 10,
  cameraId = "cam-01",
  loop = true,
): string {
  const baseUrl = getBaseUrl();
  const params = new URLSearchParams({
    fps: String(fps),
    camera_id: cameraId,
    loop: String(loop),
  });
  return `${baseUrl}/api/v1/video/missions/${encodeURIComponent(missionId)}/stream?${params.toString()}`;
}

export function getFrameImageUrl(
  missionId: string,
  frameIndex: number,
): string {
  const baseUrl = getBaseUrl();
  return `${baseUrl}/api/v1/video/missions/${encodeURIComponent(missionId)}/frames/${frameIndex}/image`;
}

export async function listFrames(
  missionId: string,
  limit = 100,
): Promise<{
  mission_id: string;
  count: number;
  frames: FrameMetadata[];
}> {
  const response = await api.get(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/frames`,
    {
      params: { limit },
    },
  );
  return response.data;
}

export async function getMissionFrames(
  missionId: string,
  limit = 100,
): Promise<{
  mission_id: string;
  count: number;
  frames: Frame[];
}> {
  return listFrames(missionId, limit);
}

export async function getFrame(
  missionId: string,
  frameIndex: number,
): Promise<FrameMetadata> {
  const response = await api.get(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/frames/${frameIndex}`,
  );
  return response.data;
}

export async function createSnapshot(
  missionId: string,
  frameIndex: number,
  cameraId?: string | null,
  notes?: string | null,
): Promise<SnapshotRecord> {
  const response = await api.post(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/snapshots`,
    {
      frame_index: frameIndex,
      camera_id: cameraId ?? null,
      notes: notes ?? null,
    },
  );
  return response.data;
}

export async function listSnapshots(
  missionId: string,
  limit = 100,
): Promise<{
  mission_id: string;
  count: number;
  snapshots: SnapshotRecord[];
}> {
  const response = await api.get(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/snapshots`,
    {
      params: { limit },
    },
  );
  return response.data;
}

export async function getSnapshot(
  missionId: string,
  snapshotId: string,
): Promise<SnapshotRecord> {
  const response = await api.get(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/snapshots/${encodeURIComponent(snapshotId)}`,
  );
  return response.data;
}

export function getSnapshotImageUrl(
  missionId: string,
  snapshotId: string,
): string {
  const baseUrl = getBaseUrl();
  return `${baseUrl}/api/v1/video/missions/${encodeURIComponent(missionId)}/snapshots/${encodeURIComponent(snapshotId)}/image`;
}

export async function deleteSnapshot(
  missionId: string,
  snapshotId: string,
): Promise<{ deleted: boolean; snapshot_id: string }> {
  const response = await api.delete(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/snapshots/${encodeURIComponent(snapshotId)}`,
  );
  return response.data;
}

export async function startRecording(
  missionId: string,
  cameraId?: string | null,
): Promise<RecordingSession> {
  const response = await api.post(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/recording/start`,
    {
      camera_id: cameraId ?? null,
    },
  );
  return response.data;
}

export async function stopRecording(
  missionId: string,
  recordingId?: string | null,
): Promise<RecordingSession> {
  const response = await api.post(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/recording/stop`,
    null,
    {
      params: recordingId ? { recording_id: recordingId } : undefined,
    },
  );
  return response.data;
}

export async function getRecordingStatus(
  missionId: string,
): Promise<RecordingStatusResponse> {
  const response = await api.get(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/recording/status`,
  );
  return response.data;
}

export async function listRecordings(
  missionId: string,
): Promise<{
  mission_id: string;
  count: number;
  recordings: RecordingSession[];
}> {
  const response = await api.get(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/recordings`,
  );
  return response.data;
}

export async function detectFrame(
  missionId: string,
  frameIndex: number,
  model = "yolo11n.pt",
  confidence = 0.25,
): Promise<DetectionResult> {
  const response = await api.post(
    `/api/v1/video/missions/${encodeURIComponent(missionId)}/frames/${frameIndex}/detect`,
    null,
    {
      params: {
        model,
        confidence,
      },
    },
  );
  return response.data;
}