import { api, apiData } from "./api";

export type OrientationSnapshot = {
  state: "stopped" | "starting" | "running" | "error";
  running: boolean;
  error: string | null;
  camera_index: number;
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
  decision_state?: "stopped" | "starting" | "analyzing" | "detected" | "uncertain" | "error";
};

const baseUrl = String(api.defaults.baseURL).replace(/\/$/, "");

export function startOrientation(): Promise<OrientationSnapshot> {
  return apiData({ method: "POST", url: "/orientation/live/start" });
}

export function stopOrientation(): Promise<OrientationSnapshot> {
  return apiData({ method: "POST", url: "/orientation/live/stop" });
}

export function orientationVideoUrl(runId: number): string {
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
