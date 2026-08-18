import { api } from "./client";
import type {
  DetectionResult,
  Frame,
} from "../types/video";

export async function getMissionFrames(
  missionId: string,
  limit = 100,
): Promise<{
  mission_id: string;
  count: number;
  frames: Frame[];
}> {
  const response = await api.get(
    `/api/v1/video/missions/${missionId}/frames`,
    {
      params: { limit },
    },
  );

  return response.data;
}

export async function getFrame(
  missionId: string,
  frameIndex: number,
): Promise<Frame> {
  const response = await api.get(
    `/api/v1/video/missions/${missionId}/frames/${frameIndex}`,
  );

  return response.data;
}

export function getFrameImageUrl(
  missionId: string,
  frameIndex: number,
): string {
  const baseUrl =
    import.meta.env.VITE_API_BASE_URL ??
    "http://127.0.0.1:8000";

  return `${baseUrl}/api/v1/video/missions/${missionId}/frames/${frameIndex}/image`;
}

export async function detectFrame(
  missionId: string,
  frameIndex: number,
  model = "yolo11n.pt",
  confidence = 0.25,
): Promise<DetectionResult> {
  const response = await api.post(
    `/api/v1/video/missions/${missionId}/frames/${frameIndex}/detect`,
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