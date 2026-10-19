import { api } from "./api";

export type SortingTelemetryPayload = Record<string, unknown>;

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
