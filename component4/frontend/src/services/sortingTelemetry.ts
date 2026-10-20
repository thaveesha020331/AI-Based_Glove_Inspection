import { api, apiData } from "./api";

export type SortingTelemetryPayload = Record<string, unknown>;

export type SortingControl = {
  automatic_enabled: boolean;
  expected_orientation: "LeftHand" | "RightHand";
  camera_light_requested: boolean;
  warning_active: boolean;
  warning_threshold: number;
  consecutive_rejects: number;
  total_decisions: number;
  total_rejected: number;
  last_action: Record<string, unknown> | null;
  last_error: string | null;
  relay_roles: Record<string, string>;
};

export function configureSortingControl(payload: {
  expected_orientation?: "LeftHand" | "RightHand";
  automatic_enabled?: boolean;
}): Promise<SortingControl> {
  return apiData({ method: "PATCH", url: "/sorting/control", data: payload });
}

export function setCameraLight(on: boolean): Promise<SortingControl> {
  return apiData({ method: "POST", url: "/sorting/control/light", data: { on } });
}

export function resetSortingWarning(): Promise<SortingControl> {
  return apiData({ method: "POST", url: "/sorting/control/warning/reset" });
}

export function subscribeSortingTelemetry(
  onData: (data: SortingTelemetryPayload) => void,
  onError: () => void,
): () => void {
  const baseUrl = String(api.defaults.baseURL ?? "").replace(/\/$/, "");
  const source = new EventSource(`${baseUrl}/sorting/stream`);
  source.onmessage = (event) => {
    onData(JSON.parse(event.data) as SortingTelemetryPayload);
  };
  source.onerror = onError;
  return () => source.close();
}
