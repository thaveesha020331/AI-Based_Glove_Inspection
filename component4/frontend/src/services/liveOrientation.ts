import { api, apiData } from "./api";

export type OrientationSnapshot = {
  state: "stopped" | "starting" | "running" | "error";
  mode: "orientation" | "defect" | null;
  running: boolean;
  error: string | null;
  camera_index: number;
  camera_auto_exposure: boolean;
  camera_auto_exposure_supported: boolean | null;
  camera_exposure: number;
  camera_gain: number;
  camera_manual_exposure_supported: boolean | null;
  camera_actual_exposure: number | null;
  camera_actual_gain: number | null;
  model: string;
  classes: string[];
  raw_prediction: string | null;
  raw_confidence: number | null;
  stable_prediction: string | null;
  stable_confidence: number | null;
  probabilities: Record<string, number>;
  fps: number;
  inference_ms: number | null;
  frame_count: number;
  stability_window: number;
  minimum_confidence: number;
  defect_model: string | null;
  defect_minimum_confidence: number;
  defective: boolean;
  defect_category: string | null;
  defect_confidence: number | null;
  defect_detections: Array<{
    class_id: number;
    category: string;
    confidence: number;
    box: number[];
  }>;
  defect_inference_ms: number | null;
  defect_ready: boolean;
  decision_state?: "stopped" | "starting" | "analyzing" | "detected" | "clear" | "uncertain" | "error";
};

const baseUrl = String(api.defaults.baseURL).replace(/\/$/, "");

export function startOrientation(): Promise<OrientationSnapshot> {
  return apiData({ method: "POST", url: "/orientation/live/start", data: { mode: "orientation" } });
}

export function startDefectDetection(): Promise<OrientationSnapshot> {
  return apiData({ method: "POST", url: "/orientation/live/start", data: { mode: "defect" } });
}

export function stopOrientation(): Promise<OrientationSnapshot> {
  return apiData({ method: "POST", url: "/orientation/live/stop" });
}

export function setCameraExposure(exposure: number): Promise<OrientationSnapshot> {
  return apiData({ method: "PATCH", url: "/orientation/live/camera", data: { exposure } });
}

export function orientationVideoUrl(runId: number): string {
  return `${baseUrl}/orientation/live/orientation-video?run=${runId}`;
}

export function defectVideoUrl(runId: number): string {
  return `${baseUrl}/orientation/live/video?run=${runId}`;
}

export function subscribeOrientation(
  onSnapshot: (snapshot: OrientationSnapshot) => void,
  onError: () => void,
): () => void {
  const source = new EventSource(`${baseUrl}/orientation/live/stream`);
  source.addEventListener("orientation", (event) => {
    onSnapshot(JSON.parse((event as MessageEvent<string>).data) as OrientationSnapshot);
  });
  source.onerror = onError;
  return () => source.close();
}
